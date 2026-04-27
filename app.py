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

# 3. Station Mileage Mapping
MAP_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0, "Start/Finish": 25.0}
MAP_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0, "Start/Finish": 20.0}

def get_status(row, mode):
    m_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    furthest_station = ""
    last_time_str = ""
    current_lap = 1
    
    # CASE-INSENSITIVE DNF CHECK
    row_as_string = " ".join(row.fillna("").astype(str)).lower()
    is_dnf_anywhere = "dnf" in row_as_string

    for col_name, val in row.items():
        val_str = str(val).strip().lower() if pd.notnull(val) else ""
        if val_str == "": continue

        base_header = col_name.split('.')[0].strip()
        if "Start/Finish" in base_header: base_header = "Arrive S/F"

        if base_header in m_map:
            try: lap_num = (int(col_name.split('.')[-1]) + 1) if "." in col_name else 1
            except: lap_num = 1
            
            # Skip if the sheet has entries for laps beyond the race limit
            if lap_num > max_loops: continue
            
            calc_miles = ((lap_num - 1) * loop_dist) + m_map[base_header]
            
            if ":" in val_str or "dnf" in val_str:
                if calc_miles >= max_miles:
                    max_miles = calc_miles
                    furthest_station = base_header
                    current_lap = lap_num
            
            if ":" in val_str:
                if calc_miles >= (max_miles - 0.1):
                    last_time_str = val_str

    # HARD CAPS: No extra miles or loops
    if max_miles > (max_loops * loop_dist):
        max_miles = (max_loops * loop_dist)
    if current_lap > max_loops:
        current_lap = max_loops

    if max_miles == 0 and not last_time_str:
        return "DNS", 0.0, "", 999999, 1

    try:
        t_parsed = pd.to_datetime(last_time_str, errors='coerce').time()
        sec = t_parsed.hour * 3600 + t_parsed.minute * 60
        total_sec = sec - (6 * 3600) if t_parsed.hour >= 14 else (sec + 86400) - (6 * 3600)
        time_str = f"{total_sec//3600}h {(total_sec%3600)//60:02d}m"
        time_checkin = t_parsed.strftime('%I:%M %p')
    except:
        time_str, total_sec, time_checkin = "---", 999999, ""

    if max_miles >= (max_loops * loop_dist):
        status_text = "Finished!"
    elif is_dnf_anywhere:
        status_text = "DNF"
    else:
        status_text = f"<b>{furthest_station}</b><br>{time_checkin}" if furthest_station else "Started"

    return status_text, max_miles, time_str, total_sec, current_lap

@st.cache_data(ttl=60)
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
            th { background-color: #f0f2f6; text-align: center; padding: 12px; font-weight: bold; }
            td { padding: 12px; border-bottom: 1px solid #eee; vertical-align: middle; text-align: center; }
            tr:hover { background-color: #fafafa; }
            /* Keep Runner Names left-aligned for readability */
            td:nth-child(2) { text-align: left; }
            </style>
            """, unsafe_allow_html=True
        )
        st.write(html_table, unsafe_allow_html=True)
except Exception as e:
    st.error(f"Syncing data... ({e})")
