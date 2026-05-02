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

STATION_MAP = {
    (1, 0): 6,  (1, 1): 7,  (1, 2): 8,  (1, 3): 11,
    (2, 0): 12, (2, 1): 13, (2, 2): 14, (2, 3): 17,
    (3, 0): 18, (3, 1): 19, (3, 2): 20, (3, 3): 23,
    (4, 0): 24, (4, 1): 25, (4, 2): 26, (4, 3): 29,
    (5, 0): 30, (5, 1): 31, (5, 2): 32, (5, 3): 35
}

def parse_to_race_time(time_str):
    """Converts a string like '11:05' or '11:05 AM' to minutes since 6:00 AM."""
    try:
        clean_time = re.sub(r'[^0-9:]', '', str(time_str))
        h, m = map(int, clean_time.split(':'))
        # Adjust for PM if not specified but before 6 (assuming race duration)
        if h < 6: h += 12 
        arrival_dt = datetime.datetime(2026, 5, 2, h, m)
        delta = arrival_dt - START_TIME_DT
        return max(0, int(delta.total_seconds() // 60))
    except:
        return None

def calculate_metrics(row, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles, last_st, last_time_str, current_lap = 0.0, "Start", "6:00 AM", 0
    last_race_mins = 0

    # 1. Find Furthest Recorded Point
    for lap in range(1, max_loops + 1):
        for i in range(4):
            col_idx = STATION_MAP.get((lap, i))
            if col_idx is not None and col_idx < len(row):
                val = str(row.iloc[col_idx]).strip()
                if any(c.isdigit() for c in val):
                    dist = ((lap - 1) * loop_dist) + m_list[i]
                    if dist >= max_miles:
                        max_miles, last_st, last_time_str, current_lap = dist, STATION_NAMES[i], val, lap
                        m = parse_to_race_time(val)
                        if m: last_race_mins = m

    # 2. MPH Calculation based on Last Seen Time (Actual Movement)
    speed = 0.0
    if max_miles > 0 and last_race_mins > 0:
        speed = max_miles / (last_race_mins / 60)
    
    race_time_fmt = f"{last_race_mins // 60}h {last_race_mins % 60}m"

    # 3. Expected Prediction
    curr_idx = STATION_NAMES.index(last_st)
    next_idx = (curr_idx + 1) % 4
    next_st_name = STATION_NAMES[next_idx]
    l_idx = current_lap + 1 if (next_idx == 0 and curr_idx == 3) else current_lap
    next_dist = ((l_idx - 1) * loop_dist) + m_list[next_idx]
    
    expected_html = "---"
    if speed > 0 and max_miles < (max_loops * loop_dist):
        mins_to_next = ((next_dist - max_miles) / speed) * 60
        arrival_dt = START_TIME_DT + datetime.timedelta(minutes=last_race_mins + mins_to_next)
        expected_html = f"<div class='expected-box'>{next_st_name}<br><span class='sub-text'>{arrival_dt.strftime('%-I:%M %p')}</span></div>"

    status_html = f"<div class='status-box'>{last_st}<br><span class='sub-text'>{last_time_str}</span></div>"
    if max_miles >= (max_loops * loop_dist):
        status_html, expected_html = "<b>FINISHED!</b>", "---"

    # 4. Sorting Logic: Distance first (desc), then Race Time (asc)
    # We use a large multiplier for miles and subtract minutes so smaller time = higher score
    sort_val = (max_miles * 10000) - last_race_mins

    return status_html, max_miles, f"{speed:.1f}", expected_html, race_time_fmt, sort_val

# 3. Data Loader
@st.cache_data(ttl=0)
def load_data(buster):
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={buster}"
    try:
        res = requests.get(url, timeout=10)
        return pd.read_csv(io.StringIO(res.text), header=None, dtype=str)
    except: return None

# 4. Main App Execution
if 'buster' not in st.session_state: 
    st.session_state['buster'] = int(time.time())

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
                status, miles, mph, expected, race_time, s_val = calculate_metrics(row, view_mode)
                results.append({
                    "Pos": 0, "Name": name, "Bib": bib, "Miles": miles,
                    "Status (Last Seen)": status, "Expected Next": expected, 
                    "MPH": mph, "Race Time": race_time, "sort_val": s_val
                })
        except: continue

    if results:
        final_df = pd.DataFrame(results).sort_values(by=['sort_val'], ascending=False)
        final_df['Pos'] = range(1, len(final_df) + 1)
        cols = ["Pos", "Name", "Bib", "Miles", "Status (Last Seen)", "Expected Next", "MPH", "Race Time"]
        st.write(final_df[cols].to_html(escape=False, index=False), unsafe_allow_html=True)
