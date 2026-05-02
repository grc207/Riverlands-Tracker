import streamlit as st
import pandas as pd
import datetime
import requests
import io
import time
import re

# 1. Setup & Styling
st.set_page_config(page_title="Riverlands 100 Live", layout="wide")

st.markdown("""
    <style>
    th { text-align: center !important; background-color: #f2f2f2; font-size: 0.9em; }
    td { text-align: center !important; border-bottom: 1px solid #ddd; vertical-align: middle !important; }
    td:nth-child(2) { text-align: left !important; font-weight: bold; min-width: 150px;}
    .status-box { line-height: 1.2; font-weight: bold; color: #1e3a8a; }
    .expected-box { line-height: 1.2; font-weight: bold; color: #b45309; }
    .sub-text { font-size: 0.85em; color: #666; font-weight: normal; }
    </style>
    """, unsafe_allow_html=True)

# 2. Timing & Constants
START_TIME_DT = datetime.datetime(2026, 5, 2, 6, 0, 0)
STATION_NAMES = ["Middle Out", "Conant Rd", "Middle Back", "Arrive S/F"]
MILES_100 = [4.5, 13.0, 20.5, 25.0]
MILES_RELAY = [3.5, 10.5, 16.5, 20.0]

# Mapping based on your pattern: Lap 1 (6,7,8,11), Lap 2 (12,13,14,17), etc.
STATION_MAP = {
    (1, 0): 6,  (1, 1): 7,  (1, 2): 8,  (1, 3): 11,
    (2, 0): 12, (2, 1): 13, (2, 2): 14, (2, 3): 17,
    (3, 0): 18, (3, 1): 19, (3, 2): 20, (3, 3): 23,
    (4, 0): 24, (4, 1): 25, (4, 2): 26, (4, 3): 29,
    (5, 0): 30, (5, 1): 31, (5, 2): 32, (5, 3): 35
}

def parse_to_minutes(time_str):
    """Converts sheet time to minutes elapsed since 6:00 AM."""
    try:
        t_str = str(time_str).strip().upper()
        # Handle AM/PM if present
        if 'M' in t_str:
            pt = datetime.datetime.strptime(t_str, '%I:%M %p')
        else:
            # Handle HH:MM
            pt = datetime.datetime.strptime(t_str, '%H:%M')
        
        # Create full datetime for today
        dt = datetime.datetime(2026, 5, 2, pt.hour, pt.minute)
        
        # If time is technically 'before' 6am (like 1:00 AM), assume it's next day/overnight
        if pt.hour < 6:
            dt += datetime.timedelta(days=1)
            
        delta = dt - START_TIME_DT
        return max(0, int(delta.total_seconds() // 60))
    except:
        return None

def calculate_metrics(row, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    last_st = "Start"
    last_time_str = "6:00 AM"
    last_race_mins = 0
    current_lap = 0

    # Find Furthest Point
    for lap in range(1, max_loops + 1):
        for i in range(4):
            col_idx = STATION_MAP.get((lap, i))
            if col_idx and col_idx < len(row):
                val = str(row.iloc[col_idx]).strip()
                if any(c.isdigit() for c in val):
                    dist = ((lap - 1) * loop_dist) + m_list[i]
                    # We accept this as the furthest point
                    if dist >= max_miles:
                        mins = parse_to_minutes(val)
                        if mins is not None:
                            max_miles = dist
                            last_st = STATION_NAMES[i]
                            last_time_str = val
                            last_race_mins = mins
                            current_lap = lap

    # MPH Calculation
    speed = 0.0
    if max_miles > 0 and last_race_mins > 0:
        speed = max_miles / (last_race_mins / 60)
    
    race_time_display = f"{last_race_mins // 60}h {last_race_mins % 60}m"

    # Expected Next
    expected_html = "---"
    if speed > 0 and max_miles < (max_loops * loop_dist):
        curr_idx = STATION_NAMES.index(last_st)
        next_idx = (curr_idx + 1) % 4
        next_st_name = STATION_NAMES[next_idx]
        l_idx = current_lap + 1 if (next_idx == 0 and curr_idx == 3) else current_lap
        next_dist = ((l_idx - 1) * loop_dist) + m_list[next_idx]
        
        mins_to_next = ((next_dist - max_miles) / speed) * 60
        eta_dt = START_TIME_DT + datetime.timedelta(minutes=last_race_mins + mins_to_next)
        expected_html = f"<div class='expected-box'>{next_st_name}<br><span class='sub-text'>{eta_dt.strftime('%-I:%M %p')}</span></div>"

    status_html = f"<div class='status-box'>{last_st}<br><span class='sub-text'>{last_time_str}</span></div>"
    if max_miles >= (max_loops * loop_dist):
        status_html, expected_html = "<b>FINISHED!</b>", "---"

    # SORTING: Primary = Miles (High to Low), Secondary = Race Minutes (Low to High)
    # We use (Miles * 10000) - RaceMinutes to create a single sortable rank
    sort_rank = (max_miles * 10000) - last_race_mins

    return status_html, max_miles, f"{speed:.1f}", expected_html, race_time_display, sort_rank

# 3. Data Loader
@st.cache_data(ttl=0)
def load_data(buster):
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={buster}"
    try:
        res = requests.get(url, timeout=10)
        return pd.read_csv(io.StringIO(res.text), header=None, dtype=str)
    except: return None

# 4. Main
if 'buster' not in st.session_state: st.session_state['buster'] = int(time.time())
raw_df = load_data(st.session_state['buster'])

if raw_df is not None:
    st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Tracker</h1>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns([3, 1])
    with col_a:
        view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
    with col_b:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.session_state['buster'] = int(time.time())
            st.rerun()

    results = []
    for i in range(len(raw_df)):
        row = raw_df.iloc[i]
        try:
            name, bib_str = str(row.iloc[0]).strip(), str(row.iloc[1]).strip()
            if not bib_str.isdigit() or len(name) < 2: continue
            
            bib = int(bib_str)
            is_relay = 400 <= bib < 500
            if (view_mode == "Relay") == is_relay:
                status, miles, mph, expected, race_time, rank = calculate_metrics(row, view_mode)
                results.append({
                    "Pos": 0, "Name": name, "Bib": bib, "Miles": miles,
                    "Status (Last Seen)": status, "Expected Next": expected, 
                    "MPH": mph, "Race Time": race_time, "rank": rank
                })
        except: continue

    if results:
        final_df = pd.DataFrame(results).sort_values(by='rank', ascending=False)
        final_df['Pos'] = range(1, len(final_df) + 1)
        cols = ["Pos", "Name", "Bib", "Miles", "Status (Last Seen)", "Expected Next", "MPH", "Race Time"]
        st.write(final_df[cols].to_html(escape=False, index=False), unsafe_allow_html=True)
