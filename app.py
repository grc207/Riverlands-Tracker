import streamlit as st
import pandas as pd
import datetime
import requests
import io
import time
import re

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Live", layout="wide")

st.markdown("""
    <style>
    th { text-align: center !important; background-color: #f2f2f2; }
    td { text-align: center !important; border-bottom: 1px solid #ddd; vertical-align: middle !important; }
    .status-box { line-height: 1.2; font-weight: bold; color: #1e3a8a; }
    .expected-box { line-height: 1.2; font-weight: bold; color: #b45309; }
    .sub-text { font-size: 0.85em; color: #666; font-weight: normal; }
    </style>
    """, unsafe_allow_html=True)

# 2. Hardcoded Essentials
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
STATION_NAMES = ["Middle Out", "Conant Rd", "Middle Back", "Arrive S/F"]
M_100 = [4.5, 13.0, 20.5, 25.0]
M_RELAY = [3.5, 10.5, 16.5, 20.0]

# YOUR SPECIFIC COLUMNS
MAP = {
    1: [6, 7, 8, 11],
    2: [12, 13, 14, 17],
    3: [18, 19, 20, 23],
    4: [24, 25, 26, 29],
    5: [30, 31, 32, 35]
}

def clean_time_to_minutes(val):
    try:
        val = str(val).strip().upper()
        if ":" not in val: return None
        ts = pd.to_datetime(val).time()
        dt = datetime.datetime(2026, 5, 2, ts.hour, ts.minute)
        if ts.hour < 6: dt += datetime.timedelta(days=1)
        return int((dt - START_TIME).total_seconds() // 60)
    except:
        return None

def get_runner_data(row, mode):
    dist_list = M_100 if mode == "100 Miler" else M_RELAY
    loop_size = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    best_dist, best_stat, best_time_str, best_time_mins, best_loop = 0.0, "Start", "---", 0, 1
    
    # SEQUENTIAL LOCK: Runner must pass through laps in order
    for lap in range(1, max_loops + 1):
        lap_cols = MAP[lap]
        lap_found = False
        for i, col_idx in enumerate(lap_cols):
            if col_idx < len(row):
                val = row.iloc[col_idx]
                mins = clean_time_to_minutes(val)
                if mins is not None:
                    best_dist = ((lap - 1) * loop_size) + dist_list[i]
                    best_time_str = str(val).strip()
                    best_time_mins = mins
                    best_stat = STATION_NAMES[i]
                    best_loop = lap
                    lap_found = True
        if not lap_found: break
            
    return best_dist, best_stat, best_time_str, best_time_mins, best_loop

# 3. Load
@st.cache_data(ttl=0)
def load():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    res = requests.get(url)
    return pd.read_csv(io.StringIO(res.text), header=None, dtype=str)

df = load()
view = st.radio("Race Category:", ["100 Miler", "Relay"], horizontal=True)

results = []
for i in range(len(df)):
    row = df.iloc[i]
    name, bib = str(row.iloc[0]), str(row.iloc[1])
    
    if bib.isdigit():
        b_val = int(bib)
        if (view == "Relay") == (400 <= b_val < 500):
            miles, stat, t_str, t_mins, loop = get_runner_data(row, view)
            
            # MPH & Race Time
            mph = round(miles / (t_mins / 60), 1) if t_mins > 0 else 0.0
            r_time = f"{t_mins // 60}h {t_mins % 60}m"
            
            # Expected Next Calculation
            expected_html = "---"
            if mph > 0 and miles < (4 * 25.0 if view == "100 Miler" else 5 * 20.0):
                curr_idx = STATION_NAMES.index(stat)
                next_idx = (curr_idx + 1) % 4
                next_st_name = STATION_NAMES[next_idx]
                target_lap = loop + 1 if (next_idx == 0 and curr_idx == 3) else loop
                
                dist_list = M_100 if view == "100 Miler" else M_RELAY
                l_size = 25.0 if view == "100 Miler" else 20.0
                next_dist = ((target_lap - 1) * l_size) + dist_list[next_idx]
                
                mins_to_next = ((next_dist - miles) / mph) * 60
                arrival = START_TIME + datetime.timedelta(minutes=t_mins + mins_to_next)
                expected_html = f"<div class='expected-box'>{next_st_name}<br><span class='sub-text'>{arrival.strftime('%-I:%M %p')}</span></div>"

            # Sort: Miles (Desc), then Minutes (Asc)
            sort_key = (miles * 10000) - t_mins
            
            results.append({
                "Pos": 0, "Name": name, "Bib": bib, "Loop": loop, "Miles": miles,
                "Status (Last Seen)": f"<div class='status-box'>{stat}<br><span class='sub-text'>{t_str}</span></div>",
                "Expected Next": expected_html, "MPH": mph, "Race Time": r_time, "sort": sort_key
            })

if results:
    f_df = pd.DataFrame(results).sort_values("sort", ascending=False)
    f_df["Pos"] = range(1, len(f_df) + 1)
    display_cols = ["Pos", "Name", "Bib", "Loop", "Miles", "Status (Last Seen)", "Expected Next", "MPH", "Race Time"]
    st.write(f_df[display_cols].to_html(escape=False, index=False), unsafe_allow_html=True)
