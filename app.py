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

# 2. st.info Disclaimer
st.info("**Disclaimer:** This is an independent project and is not maintained by the race director. "
        "All information may not be timely or accurate and should NOT be accepted as official!\n\n"
        "Some updates may take a few minutes to refresh.")

# 3. Timer Logic
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
st.write("**Elapsed Race Time**")

# 4. Station Configuration
STATIONS_100 = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}

STATIONS_RELAY = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

def get_status(row, mode):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    s_list = STATIONS_100 if mode == "100 Miler" else STATIONS_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    total_race_dist = 100.0
    
    # 1. DNF CHECK (ABSOLUTE PRIORITY)
    row_str = " ".join(row.astype(str).fillna("")).lower()
    is_dnf = "dnf" in row_str
    
    max_miles, furthest_station, last_time_str = 0.0, "", ""
    sf_count = 0 # Track how many Arrive S/F columns we've passed

    for col_name, val in row.items():
        val_str = str(val).strip().lower() if pd.notnull(val) else ""
        if val_str == "": continue

        base_header = col_name.split('.')[0].strip()
        if "Start/Finish" in base_header: base_header = "Arrive S/F"

        if base_header in m_map:
            if base_header == "Arrive S/F":
                sf_count += 1
            
            # 2. STRICT COLUMN CAPPING: Ignore data past the final lap terminus
            if sf_count > max_loops:
                break
                
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

    if max_miles > total_race_dist: max_miles = total_race_dist
    calculated_loop = 1 if max_miles == 0 else int((max_miles - 0.01) // loop_dist) + 1

    # Time Parsing with 2 PM Rule
    total_sec, time_str, time_checkin, avg_mph = 999999, "---", "", 0.0
    if last_time_str:
        try:
            t_parsed = pd.to_datetime(last_time_str, errors='coerce').time()
            sec_midnight = t_parsed.hour * 3600 + t_parsed.minute * 60
            total_sec_from_sat = sec_midnight + 86400 if t_parsed.hour < 14 else sec_midnight
            total_sec = total_sec_from_sat - 21600
            time_str = f"{total_sec//3600}h {(total_sec%3600)//60:02d}m"
            time_checkin = t_parsed.strftime('%I:%M %p')
            if total_sec > 0:
                avg_mph = max_miles / (total_sec / 3600)
        except: pass

    # 3. DNF FLAG OVERRIDE (Ensures DNF wins even if text is in a 100-mile column)
    if is_dnf:
        return "DNF", max_miles, "---", 999999, calculated_loop, "---"
        
    if max_miles >= total_race_dist:
        return "Finished!", total_race_dist, time_str, total_sec, int(total_race_dist // loop_dist), "N/A"
    
    if max_miles == 0 and not last_time_str:
        return "DNS", 0.0, "", 999999, 1, "---"

    # Prediction Logic
    next_loc_display = "---"
    if avg_mph > 0:
        current_idx = s_list.index(furthest_station) if furthest_station in s_list else -1
        next_idx = (current_idx + 1) % len(s_list)
        next_base = s_list[next_idx]
        next_lap = calculated_loop + 1 if next_idx == 0 else calculated_loop
        next_miles = ((next_lap - 1) * loop_dist) + m_map[next_base]
        
        if next_miles <= total_race_dist:
            dist_to_go = next_miles - max_miles
            sec_to_next = (dist_to_go / avg_mph) * 3600
            arrival_total_sec = (total_sec + 21600 + sec_to_next) % 86400
            arrival_time = (datetime.datetime(2026, 1, 1, 0, 0) + datetime.timedelta(seconds=arrival_total_sec)).strftime('%I:%M %p')
            next_loc_display = f"{next_base}<br><hr style='margin:4px 0; border:0; border-top:1px solid #ddd;'>{arrival_time}"

    status_text = f"<b>{furthest_station}</b><br>{time_checkin}" if furthest_station else "Started"
    return status_text, max_miles, time_str, total_sec, calculated_loop, next_loc_display

@st.cache_data(ttl=30)
def load_data(mode, query=""):
    df = pd.read_csv(f"https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    mask = df['Team/Runner'].isna() | (df['Team/Runner'].astype(str).str.strip() == "")
    gap = df[mask].index[0] if len(df[mask]) > 0 else len(df)
    active_df = (df.loc[:gap-1] if mode == "Relay" else df.loc[gap+1:]).copy()
    active_df = active_df[active_df['Team/Runner'].notna() & (active_df['Team/Runner'].astype(str).str.strip() != "")]
    
    bib_col = [c for c in df.columns if 'Bib' in c][0]
    active_df[bib_col] = active_df[bib_col].astype(str).replace(r'\.0$', '', regex=True)

    if query:
        active_df = active_df[active_df['Team/Runner'].astype(str).str.contains(query, case=False) | active_df[bib_col].astype(str).contains(query, case=False)]
    
    results = []
    for _, row in active_df.iterrows():
        status, miles, t_disp, t_sec, lap, next_loc = get_status(row, mode)
        is_inactive = any(x in status for x in ["DNF", "DNS"])
        avg_speed = "---" if is_inactive else f"{(miles / (t_sec / 3600)):.2f} mph" if t_sec > 0 and t_sec != 999999 else "0.00 mph"
        results.append({
            "Pos": 0, "Team/Runner": row['Team/Runner'], "Bib": row[bib_col],
            "Status": status, "Total Miles": miles, "Race Time": "---" if is_inactive else t_disp,
            "Avg Speed": avg_speed, "Next Expected": next_loc, "SortSeconds": t_sec, "Lap": lap if status != "DNS" else ""
        })
    
    if not results: return pd.DataFrame()
    
    # Sorting: DNF/DNS go to bottom
    full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'SortSeconds'], ascending=[False, True])
    mask_rank = (~full_df['Status'].astype(str).str.contains("DNF|DNS", na=False)) & (full_df['Total Miles'] > 0)
    full_df.loc[mask_rank, 'Pos'] = range(1, mask_rank.sum() + 1)
    full_df.loc[~mask_rank, 'Pos'] = None
    return full_df

# 5. Leaderboard UI
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
