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

# 2. Disclaimer (Moved to Top)
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 0.9em; padding: 10px; background-color: #f9f9f9; border-radius: 5px; border: 1px solid #eee; margin-bottom: 20px;'>
        <b>IMPORTANT DISCLAIMER:</b> All times and standings shown are unofficial and intended for spectator 
        tracking purposes only. Race-day conditions or technical delays may impact real-time accuracy. 
        Official results will be posted following the conclusion of the event.
    </div>
    """, unsafe_allow_html=True
)

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
    st.subheader(f"⏱️ Start in: {format_delta_hhh(START_TIME - now)}")
else:
    elapsed_diff = now - START_TIME
    display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
    st.subheader(f"⏱️ Race Clock: {format_delta_hhh(display_elapsed)}")

# 4. Station Configuration
STATIONS_100 = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}

STATIONS_RELAY = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

def get_status(row, mode):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    s_list = STATIONS_100 if mode == "100 Miler" else STATIONS_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    total_race_dist = 100.0
    
    max_miles, furthest_station, last_time_str = 0.0, "", ""
    
    # Case-Insensitive DNF Check
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
        except:
            pass

    if max_miles >= total_race_dist:
        return "Finished!", total_race_dist, time_str, total_sec, int(total_race_dist // loop_dist), "N/A"
    
    if is_dnf:
        return "DNF", max_miles, "---", 999999, calculated_loop, "---"

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
            next_loc_display = f"{next_base
