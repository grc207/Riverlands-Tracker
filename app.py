import streamlit as st
import pandas as pd
import datetime
import requests
import io
import time
import re

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Live", layout="wide")

# 2. Hardcoded Essentials
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
STATION_NAMES = ["Middle Out", "Conant Rd", "Middle Back", "Arrive S/F"]
M_100 = [4.5, 13.0, 20.5, 25.0]
M_RELAY = [3.5, 10.5, 16.5, 20.0]

# YOUR SPECIFIC COLUMNS
# Lap 1: 6,7,8,11 | Lap 2: 12,13,14,17 | Lap 3: 18,19,20,23 | Lap 4: 24,25,26,29
MAP = {
    1: [6, 7, 8, 11],
    2: [12, 13, 14, 17],
    3: [18, 19, 20, 23],
    4: [24, 25, 26, 29],
    5: [30, 31, 32, 35] # Relay Lap 5
}

def clean_time_to_minutes(val):
    """Parse '11:05' or '11:05 AM' into minutes since 6:00 AM."""
    try:
        val = str(val).strip().upper()
        if not any(c.isdigit() for c in val): return None
        
        # Standardize format
        if ":" not in val: return None
        
        # Use pandas to handle AM/PM or 24h flexibility
        ts = pd.to_datetime(val).time()
        dt = datetime.datetime(2026, 5, 2, ts.hour, ts.minute)
        
        if ts.hour < 6: # Overnight handling
            dt += datetime.timedelta(days=1)
            
        return int((dt - START_TIME).total_seconds() // 60)
    except:
        return None

def get_runner_data(row, mode):
    dist_list = M_100 if mode == "100 Miler" else M_RELAY
    loop_size = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    best_dist = 0.0
    best_time_str = "---"
    best_time_mins = 0
    best_stat = "Start"
    
    # SEQUENTIAL LOCK: Only progress to next lap if current lap has data
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
                    lap_found = True
        
        # If no data found in this lap, DO NOT look at next lap
        if not lap_found:
            break
            
    return best_dist, best_stat, best_time_str, best_time_mins

# 3. Load
@st.cache_data(ttl=0)
def load():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    res = requests.get(url)
    return pd.read_csv(io.StringIO(res.text), header=None, dtype=str)

df = load()
view = st.sidebar.radio("Race:", ["100 Miler", "Relay"])
if st.sidebar.button("Refresh"): 
    st.cache_data.clear()
    st.rerun()

results = []
for i in range(len(df)):
    row = df.iloc[i]
    name, bib = str(row.iloc[0]), str(row.iloc[1])
    
    if bib.isdigit():
        b_val = int(bib)
        is_relay = 400 <= b_val < 500
        if (view == "Relay") == is_relay:
            miles, stat, t_str, t_mins = get_runner_data(row, view)
            
            # MPH Calculation
            mph = round(miles / (t_mins / 60), 1) if t_mins > 0 else 0.0
            
            # Race Time Display
            r_time = f"{t_mins // 60}h {t_mins % 60}m" if t_mins > 0 else "0h 0m"
            
            # SORT VAL: Higher miles = better. Lower time for same miles = better.
            sort_key = (miles * 10000) - t_mins
            
            results.append({
                "Pos": 0, "Name": name, "Bib": bib, "Miles": miles,
                "Status": f"<b>{stat}</b><br>{t_str}",
                "MPH": mph, "Race Time": r_time, "sort": sort_key
            })

# 4. Display
if results:
    f_df = pd.DataFrame(results).sort_values("sort", ascending=False)
    f_df["Pos"] = range(1, len(f_df) + 1)
    st.write(f_df[["Pos", "Name", "Bib", "Miles", "Status", "MPH", "Race Time"]].to_html(escape=False, index=False), unsafe_allow_html=True)
