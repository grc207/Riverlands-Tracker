import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup & Logo
st.set_page_config(page_title="Riverlands 100 Live Leaderboard", layout="wide")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo.jpg", use_container_width=True)
    except:
        st.write("*(Logo Placeholder: logo.jpg)*")

st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)

# 2. Timer Logic
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
RACE_LIMIT_HOURS = 32
now = datetime.datetime.now()

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

if now < START_TIME:
    st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
else:
    elapsed_diff = now - START_TIME
    display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
    st.subheader(f"⏱️ {format_delta_hhh(display_elapsed)}")

# 3. Strict Mileage Mapping
STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0, "Start/Finish": 25.0}
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0, "Start/Finish": 20.0}

def get_status(row, mode):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    total_race_dist = 100.0
    
    max_miles = 0.0
    furthest_station = ""
    last_time_str = ""
    
    # Universal Case-Insensitive DNF Check
    row_str = " ".join(row.fillna("").astype(str)).lower()
    is_dnf = "dnf" in row_str

    for col_name, val in row.items():
        val_str = str(val).strip().lower() if pd.notnull(val) else ""
        if val_str == "": continue

        base_header = col_name.split('.')[0].strip()
        if "Start/Finish" in base_header: base_header = "Arrive S/F"

        if base_header in m_map:
            try:
                lap_idx = int(col_name.split('.')[-1]) if "." in col_name else 0
                lap_num = lap_idx + 1
            except:
                lap_num = 1
            
            calc_miles = ((lap_num - 1) * loop_dist) + m_map[base_header]
            
            if ":" in val_str or "dnf" in val_str:
                if calc_miles >= max_miles:
                    max_miles = calc_miles
                    furthest_station = base_header
            
            if ":" in val_str:
                if calc_miles >= (max_miles - 0.1):
                    last_time_str = val_str

    # Final Data Cleanup
    if max_miles > total_race_dist: max_miles = total_race_dist
    
    # Loop Logic (Mileage-based to avoid Loop 5 errors)
    if max_miles == 0:
        calculated_loop = 1
    else:
        calculated_loop = int((max_miles - 0.01) // loop_dist) + 1

    if max_miles == 0 and not last_time_str:
        return "DNS", 0.0, "", 999999, 1

    # RESTORED: 2 PM Next-Day Logic
    try:
        t_parsed = pd.to_datetime(last_time_str, errors='coerce').time()
        # Convert everything to seconds since midnight
        sec_since_midnight = t_parsed.hour * 3600 + t_parsed.minute * 60
        
        # 2 PM Rule: If hour < 14 (2 PM), it's Sunday (add 24 hours)
        # If hour >= 14, it's Saturday
        if t_parsed.hour < 14:
            total_sec_from_midnight_sat = sec_since_midnight + 86400
        else:
            total_sec_from_midnight_sat = sec_since_midnight
            
        # Subtract 6:00 AM Start Time (21600 seconds)
        total_sec = total_sec_from_midnight_sat - 21600
        
        time_str = f"{total_sec//3600}h {(total_sec%3600)//60:02d}m"
        time_checkin = t_parsed.strftime('%I:%M %p')
    except:
        time_str, total_sec, time_checkin = "---", 999999, ""

    if max_miles >= total_race_dist:
        return "Finished!", total_race_dist, time_str, total_sec, int(total_race_dist // loop_dist)
    
    if is_dnf:
        return "DNF", max_miles, "---", 999999, calculated_loop
        
    status_text = f"<b>{furthest_station}</b><br>{time_checkin}" if furthest_station else "Started"
    return status_text, max_miles, time_str, total_sec, calculated_loop

@st.cache_data(ttl=30)
def load_data(mode, query=""):
    df = pd.read_csv(f"https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    
    mask = df['Team/Runner'].isna() | (df['Team/Runner'].astype(str).str.strip() == "")
    gap_indices = df[mask].index
    gap = gap_indices[0] if len(gap_indices) > 0 else len(df)
    
    active_df = (df.loc[:gap-1] if mode == "Relay" else df.loc[gap+1:]).copy()
    active_df = active_df[active_df['Team/Runner'].notna() & (active_df['Team/Runner'].astype(str).str.strip() != "")]
    
    bib_col = [c for c in df.columns if 'Bib' in c][0]
    active_df[bib_col] = active_df[bib_col].astype(str).replace(r'\.0$', '', regex=True)

    if query:
        active_df = active_df[active_df['Team/Runner'].astype(str).str.contains(query, case=False) | active_df[bib_col].astype(str).contains(query, case=False)]
    
    results = []
    for _, row in active_df.iterrows():
        status, miles, t_disp, t_sec, lap = get_status(row, mode)
        
        is_inactive = any(x in status for x in ["DNF", "DNS"])
        avg_speed = "---" if is_inactive else f"{(miles / (t_sec / 3600)):.2f} mph" if t_sec > 0 and t_sec != 999999 else "0.00 mph"
        race_time = "---" if is_inactive else t_disp

        results.append({
            "Pos": 0, "Team/Runner": row['Team/Runner'], "Bib": row[bib_col],
            "Status": status, "Total Miles": miles, "Race Time": race_time,
            "Avg Speed": avg_speed, "SortSeconds": t_sec, "Lap": lap if status != "DNS" else ""
        })
    
    if not results: return pd.DataFrame()
    full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'SortSeconds'], ascending=[False, True])
    
    mask_rank = (~full_df['Status'].astype(str).str.contains("DNF|DNS", na=False)) & (full_df['Total Miles'] > 0)
    full_df.loc[mask_rank, 'Pos'] = range(1, mask_rank.sum() + 1)
    full_df.loc[~mask_rank, 'Pos'] = None
    return full_df

# 5. UI Render
view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search_query = st.text_input("Search Name or Bib", placeholder="Search...")

try:
    master_df = load_data(view_mode, search_query)
    if not master_df.empty:
        master_df['Pos'] = master_df['Pos'].fillna('').apply(lambda x: int(x) if x != '' else '')
        html_table = master_df.drop(columns=['SortSeconds']).to_html(escape=False, index=False)
        st.markdown(
            """
            <style>
            table { width: 100%; border-collapse: collapse; font-family: sans-serif; }
            th { background-color: #f0f2f6; text-align: center !important; padding: 12px; font-weight: bold; }
            td { padding: 12px; border-bottom: 1px solid #eee; vertical-align: middle; text-align: center !important; }
            tr:hover { background-color: #fafafa; }
            td:nth-child(2), th:nth-child(2) { text-align: left !important; }
            </style>
            """, unsafe_allow_html=True
        )
        st.write(html_table, unsafe_allow_html=True)
except Exception as e:
    st.error(f"Syncing data... ({e})")
