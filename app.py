import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup & Centered Logo
st.set_page_config(page_title="Riverlands 100 Live Leaderboard", layout="wide")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo.jpg", use_container_width=True)
    except:
        st.write("*(Logo Placeholder: logo.jpg)*")

st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)

# 2. Timer & Countdown Logic
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
RACE_LIMIT_HOURS = 32
now = datetime.datetime.now()

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

with st.container():
    if now < START_TIME:
        st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
        st.write("**Hours Until Race Day!**")
    else:
        elapsed_diff = now - START_TIME
        display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
        st.subheader(f"⏱️ {format_delta_hhh(display_elapsed)}")
        st.write("**Elapsed Race Time**")

# 3. Disclaimer
st.info("**Disclaimer:** This is an independent project and is not maintained by the race director. "
        "All information may not be timely or accurate and should NOT be accepted as official!\n\n"
        "Some updates may take a few minutes to refresh.")

# 4. Station Mapping
MAP_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0, "Start/Finish": 25.0}
MAP_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0, "Start/Finish": 20.0}
STATION_ORDER = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]

def get_next_expected(status, current_station, current_miles, avg_mph, mode):
    if status in ["Finished!", "DNF", "DNS"] or avg_mph <= 0:
        return "---"
    
    m_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_size = 25.0 if mode == "100 Miler" else 20.0
    
    try:
        idx = STATION_ORDER.index(current_station)
        next_idx = (idx + 1) % len(STATION_ORDER)
        next_name = STATION_ORDER[next_idx]
    except:
        next_name = STATION_ORDER[0]

    # Fixed distance math: Next station progress vs current progress in loop
    current_lap_progress = current_miles % loop_size
    next_station_progress = m_map[next_name]
    
    dist_to_next = next_station_progress - current_lap_progress
    if dist_to_next <= 0: # Wrap to next lap
        dist_to_next += loop_size

    hours_to_next = dist_to_next / avg_mph
    pred_time = datetime.datetime.now() + datetime.timedelta(hours=hours_to_next)
    return f"{next_name} @ {pred_time.strftime('%I:%M %p')}"

def get_status(row, mode):
    m_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_miles, furthest_val, furthest_station, final_loop = 0.0, "", "Start", 1
    
    row_str = row.astype(str).str.cat()
    if ":" not in row_str: 
        return "DNS", 0.0, "", 999999, 1, "---"
    
    for col_name, val in row.items():
        val_str = str(val).strip() if pd.notnull(val) else ""
        if ":" in val_str and "dnf" not in val_str.lower():
            base_header = col_name.split('.')[0].strip()
            if any(x in base_header for x in ["Start/Finish", "Arrive S/F"]): base_header = "Arrive S/F"

            if base_header in m_map:
                try:
                    lap_num = (int(col_name.split('.')[-1]) + 1) if "." in col_name else 1
                except: lap_num = 1
                
                curr_miles = ((lap_num - 1) * loop_dist) + m_map[base_header]
                if
