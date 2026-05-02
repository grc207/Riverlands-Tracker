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

# 2. Disclaimer
st.info("**Disclaimer:** This is an independent project and is not maintained by the race director. "
        "All information may not be timely or accurate and should NOT be accepted as official!")

# 3. Timezone Logic (UTC to EDT)
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) 

# Race Date: May 2nd, 2026
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
DNS_CUTOFF = datetime.datetime(2026, 5, 2, 7, 30, 0)
RACE_LIMIT_HOURS = 32

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

if now < START_TIME:
    st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
    st.write("**Countdown to Race Start**")
else:
    elapsed_diff = now - START_TIME
    display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
    st.subheader(f"⏱️ {format_delta_hhh(display_elapsed)}")
    st.write("**Elapsed Race Time**")

# 4. Data Processing Logic
STATIONS_100 = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
STATIONS_RELAY = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

def get_status(row, mode, global_has_data):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    s_list = STATIONS_100 if mode == "100 Miler" else STATIONS_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    total_race_dist = 100.0
    
    # If the sheet has no times entered yet, show the pre-race message
    if not global_has_data:
        return "Race starts May 2nd @ 6am", 0.0, "---", 999999, 1, "---"

    row_str = " ".join(row.astype(str).fillna("")).lower()
    is_dnf = "dnf" in row_str
    max_miles, furthest_station, last_time_str = 0.0, "", ""
    sf_count = 0 

    for col_name, val in row.items():
        val_str = str(val).strip().lower() if pd.notnull(val) else ""
        if val_str == "" or ":" not in val_str: continue
        
        base_header = col_name.split('.')[0].strip()
        if "Start/Finish" in base_header: base_header = "Arrive S/F"

        if base_header in m_map:
            if base_header == "Arrive S/F": sf_count += 1
            try:
                lap_idx = int(col_name.split('.')[-1]) if "." in col_name else 0
                lap_num = lap_idx + 1
            except: lap_num = 1
            
            calc_miles = ((lap_num - 1) * loop_dist) + m_map[base_header]
            if calc_miles >= max_miles:
                max_miles = calc_miles
                furthest_station = base_header
                last_time_str = val_str

    if max_miles > total_race_dist: max_miles = total_race_dist
    calculated_loop = 1 if max_miles == 0 else int((max_miles - 0.01) // loop_dist) + 1

    total_sec, time_str, time_checkin, avg_mph = 999999, "---", "", 0.0
    if last_time_str:
        try:
            t_parsed = pd.to_datetime(last_time_str, errors='coerce').time()
            sec_midnight = t_parsed.hour * 3600 + t_parsed.minute * 60
            # Offset logic for Sat/Sun
            total_sec_from_sat = sec_midnight + 86400 if t_parsed.hour < 14 else sec_midnight
            total_sec = total_sec_from_sat - 21600 # Subtract 6am start
            time_str = f"{total_sec//3600}h {(total_sec%3600)//60:02d}m"
            time_checkin = t_parsed.strftime('%I:%M %p')
            if total_sec > 0: avg_mph = max_miles / (total_sec / 3600)
        except: pass

    if is_dnf: return "DNF", max_miles, "---", 999999, calculated_loop, "---"
    if max_miles >= total_race_dist: return "Finished!", total_race_dist, time_str, total_sec, int(total_race_dist // loop_dist), "N/A"
    
    if max_miles == 0:
        return "Not Started", 0.0, "---", 999999, 1, "<b>Middle out</b>"

    expected_display = "---"
    if avg_mph > 0:
        current_idx = s_list.index(furthest_station) if furthest_station in s_list else -1
        next_idx = (current_idx + 1) % len(s_list)
        next_base = s_list[next_idx]
        next_lap = calculated_loop + 1 if next_idx == 0 else calculated_loop
        next_miles = ((next_lap - 1) * loop_dist) + m_map[next_base]
        if next_miles <= total_race_dist:
            penalty = 1.10 if mode == "Relay" else 1.0 + (max(0, calculated_loop - 1) * 0.05)
            dist_to_go = next_miles - max_miles
            sec_to_next = (dist_to_go / avg_mph) * 3600 * penalty
            arrival_total_sec = (total_sec + 21600 + sec_to_next) % 86400
            arrival_time = (datetime.datetime(2026, 1, 1, 0, 0) + datetime.timedelta(seconds=arrival_total_sec)).strftime('%I:%M %p')
            expected_display = f"<b>{next_base}</b><br>{arrival_time}"

    return f"<b>{furthest_station}</b><br>{time_checkin}", max_miles, time_str, total_sec, calculated_loop, expected_display

@st.cache_data(ttl=30)
def load_data(mode, query=""):
    base_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    full_url = f"{base_url}&cachebust={time.time()}"

    try:
        df = pd.read_csv(full_url)
        df.columns = [str(c).strip() for c in df.columns]
        
        # 1. Identify the Bib column
        bib_col = next((c for c in df.columns if "Bib" in c), None)
        
        # 2. Identify the Runner/Team column (Ignore "Status" or columns with "Unnamed")
        name_col = next((c for c in df.columns if any(x in c for x in ["Runner", "Team"]) and "Status" not in c), None)

        if not name_col or not bib_col:
            st.error(f"Syncing Error: Missing critical columns. Found: {list(df.columns)}")
            return pd.DataFrame()
            
        # Clean Bib data
        df[bib_col] = pd.to_numeric(df[bib_col], errors='coerce')
        df = df[df[bib_col].notna()] # Drop rows where Bib is missing (headers/gaps)
        
        # CLASSIFICATION BY BIB
        is_relay_bib = (df[bib_col] >= 400) & (df[bib_col] < 500)
        active_df = df[is_relay_bib].copy() if mode == "Relay" else df[~is_relay_bib].copy()
            
        # Filter out rows where the name is "DNS" or "Status" (leftover from merged headers)
        active_df = active_df[~active_df[name_col].astype(str).str.contains("DNS|Status|Runner|Team", case=False, na=False)]
        
        # Final formatting
        active_df[bib_col] = active_df[bib_col].astype(int).astype(str)

        if mode == "100 Miler" and query:
            query = query.strip().lower()
            active_df = active_df[
                active_df[name_col].astype(str).str.lower().str.contains(query, na=False) | 
                active_df[bib_col].astype(str).str.lower().str.contains(query, na=False)
            ]
        
        # Check if any timing data exists
        station_cols = [c for c in active_df.columns if any(s in c for s in ["Middle", "Conant", "Arrive", "Start/Finish"])]
        global_has_data = active_df[station_cols].apply(lambda x: x.astype(str).str.contains(":", na=False)).any().any()
        
        results = []
        for _, row in active_df.iterrows():
            status, miles, t_disp, t_sec, lap, expected = get_status(row, mode, global_has_data)
            is_inactive = any(x in status for x in ["DNF", "DNS", "Not Started", "Race starts"])
            speed_val = "---" if (is_inactive or t_sec == 999999 or miles == 0) else f"{(miles / (t_sec / 3600)):.2f} mph"
            results.append({
                "Pos": 0, "Team/Runner": row[name_col], "Bib": row[bib_col],
                "Status": status, "Total Miles": miles, "Race Time": "---" if is_inactive else t_disp,
                "Avg Speed": speed_val, "Expected": expected, "SortSeconds": t_sec
            })
        
        if not results: return pd.DataFrame()
        
        full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'SortSeconds'], ascending=[False, True])
        mask_rank = (~full_df['Status'].astype(str).str.contains("DNF|DNS|Not Started|Race", na=False)) & (full_df['Total Miles'] > 0)
        full_df.loc[mask_rank, 'Pos'] = range(1, mask_rank.sum() + 1)
        full_df.loc[~mask_rank, 'Pos'] = None
        return full_df
        
    except Exception as e:
        st.error(f"Syncing data... ({e})")
        return pd.DataFrame()

# 5. UI Controls
ctrl_col1, ctrl_col2 = st.columns([3, 1])
with ctrl_col1:
    view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)

search_query = ""
if view_mode == "100 Miler":
    search_query = st.text_input("🔍 Search 100-Miler Name or Bib:", placeholder="Type name...")

with ctrl_col2:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 6. Table Rendering
try:
    master_df = load_data(view_mode, search_query)
    if not master_df.empty:
        master_df['Pos'] = master_df['Pos'].fillna('').apply(lambda x: int(x) if x != '' else '')
        html_table = master_df.drop(columns=['SortSeconds']).to_html(escape=False, index=False)
        st.markdown(
            """
            <style>
            table { width: 100%; border-collapse: collapse; font-family: sans-serif; border: 1px solid #bbb; }
            th { background-color: #e0e0e0; text-align: center !important; padding: 12px; font-weight: bold; border: 1px solid #bbb; color: #333; }
            td { padding: 12px; border: 1px solid #bbb; vertical-align: middle; text-align: center !important; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            tr:hover { background-color: #f1f1f1; }
            td:nth-child(2), th:nth-child(2) { text-align: left !important; }
            </style>
            """, unsafe_allow_html=True
        )
        st.write(html_table, unsafe_allow_html=True)
    elif search_query:
        st.warning(f"No results found for '{search_query}'")
except Exception as e:
    st.error(f"Error building table: {e}")
