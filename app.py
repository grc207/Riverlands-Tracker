import streamlit as st
import pandas as pd
import datetime
import requests
import io
import time

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

# 2. Timing Constants
START_H = 6
STATION_NAMES = ["Middle Out", "Conant Rd", "Middle Back", "Arrive S/F"]
M_100 = [4.5, 13.0, 20.5, 25.0]
M_RELAY = [3.5, 10.5, 16.5, 20.0]

MAP = {
    1: [6, 7, 8, 11],
    2: [12, 13, 14, 17],
    3: [18, 19, 20, 23],
    4: [24, 25, 26, 29],
    5: [30, 31, 32, 35]
}

def get_total_minutes(time_str):
    """Manually parse HH:MM to avoid datetime errors."""
    try:
        clean = str(time_str).strip().upper().replace(" AM", "").replace(" PM", "")
        if ":" not in clean: return None
        
        parts = clean.split(":")
        h = int(parts[0])
        m = int(parts[1])
        
        # Simple PM handling if someone enters 1:00 instead of 13:00
        if "PM" in str(time_str).upper() and h < 12: h += 12
        # Overnight handling: if hour is 0-5, it's the next day (Race + 24hrs)
        if h < START_H: h += 24
        
        # Minutes since 6:00 AM
        return (h * 60 + m) - (START_H * 60)
    except:
        return None

def get_runner_data(row, mode):
    dist_list = M_100 if mode == "100 Miler" else M_RELAY
    loop_size = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    # Default State
    d, s, t_str, t_mins, lp = 0.0, "Start", "---", 0, 1
    
    for lap in range(1, max_loops + 1):
        lap_cols = MAP[lap]
        found_in_lap = False
        for i, col_idx in enumerate(lap_cols):
            if col_idx < len(row):
                val = row.iloc[col_idx]
                mins = get_total_minutes(val)
                if mins is not None:
                    d = ((lap - 1) * loop_size) + dist_list[i]
                    s = STATION_NAMES[i]
                    t_str = str(val).strip()
                    t_mins = mins
                    lp = lap
                    found_in_lap = True
        if not found_in_lap: break # Sequential Lock
            
    return d, s, t_str, t_mins, lp

# 3. App Logic
@st.cache_data(ttl=0)
def load():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    res = requests.get(url)
    return pd.read_csv(io.StringIO(res.text), header=None, dtype=str)

df = load()
view = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)

results = []
for i in range(len(df)):
    row = df.iloc[i]
    name, bib = str(row.iloc[0]).strip(), str(row.iloc[1]).strip()
    
    if bib.isdigit() and len(name) > 1:
        b_val = int(bib)
        if (view == "Relay") == (400 <= b_val < 500):
            miles, stat, t_str, t_mins, loop = get_runner_data(row, view)
            
            # MPH & Race Time
            mph = round(miles / (t_mins / 60), 1) if t_mins > 0 else 0.0
            r_time = f"{t_mins // 60}h {t_mins % 60}m"
            
            # Expected Next
            expected_html = "---"
            max_d = (4 * 25.0) if view == "100 Miler" else (5 * 20.0)
            if mph > 0 and miles < max_d:
                c_idx = STATION_NAMES.index(stat)
                n_idx = (c_idx + 1) % 4
                n_st = STATION_NAMES[n_idx]
                t_lp = loop + 1 if (n_idx == 0 and c_idx == 3) else loop
                
                d_list = M_100 if view == "100 Miler" else M_RELAY
                l_sz = 25.0 if view == "100 Miler" else 20.0
                n_dist = ((t_lp - 1) * l_sz) + d_list[n_idx]
                
                eta_m = t_mins + ((n_dist - miles) / mph * 60)
                eta_h = int((eta_m + (START_H * 60)) // 60) % 24
                eta_min = int(eta_m % 60)
                ampm = "AM" if eta_h < 12 or eta_h >= 24 else "PM"
                display_h = eta_h if eta_h <= 12 else eta_h - 12
                if display_h == 0: display_h = 12
                
                expected_html = f"<div class='expected-box'>{n_st}<br><span class='sub-text'>{display_h}:{eta_min:02d} {ampm}</span></div>"

            # Sort Key
            sort_val = (miles * 10000) - t_mins
            
            results.append({
                "Pos": 0, "Name": name, "Bib": bib, "Miles": miles,
                "Status (Last Seen)": f"<div class='status-box'>{stat}<br><span class='sub-text'>{t_str}</span></div>",
                "Expected Next": expected_html, "MPH": mph, "Race Time": r_time, 
                "Loop": loop, "sort": sort_val
            })

if results:
    f_df = pd.DataFrame(results).sort_values("sort", ascending=False)
    f_df["Pos"] = range(1, len(f_df) + 1)
    cols = ["Pos", "Name", "Bib", "Miles", "Status (Last Seen)", "Expected Next", "MPH", "Race Time", "Loop"]
    st.write(f_df[cols].to_html(escape=False, index=False), unsafe_allow_html=True)
