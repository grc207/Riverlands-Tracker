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
    th { text-align: center !important; background-color: #f2f2f2; }
    td { text-align: center !important; border-bottom: 1px solid #ddd; vertical-align: middle !important; }
    td:nth-child(2) { text-align: left !important; font-weight: bold; min-width: 150px;}
    .status-box { line-height: 1.2; font-weight: bold; color: #1e3a8a; }
    .time-sub { font-size: 0.85em; color: #666; font-weight: normal; }
    </style>
    """, unsafe_allow_html=True)

# 2. Timing & Constants
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) 
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)

STATION_NAMES = ["Middle Out", "Conant Rd", "Middle Back", "Arrive S/F"]
MILES_100 = [4.5, 13.0, 20.5, 25.0]
MILES_RELAY = [3.5, 10.5, 16.5, 20.0]

# DIRECT MAPPING based on your specific column layout
STATION_MAP = {
    (1, 0): 6,  (1, 1): 7,  (1, 2): 8,  (1, 3): 11,
    (2, 0): 12, (2, 1): 13, (2, 2): 14, (2, 3): 17,
    (3, 0): 18, (3, 1): 19, (3, 2): 20, (3, 3): 23,
    (4, 0): 24, (4, 1): 25, (4, 2): 26, (4, 3): 29,
    (5, 0): 30, (5, 1): 31, (5, 2): 32, (5, 3): 35  # Pattern for Relay Lap 5
}

def is_valid_time(val):
    val_str = str(val).strip().lower()
    if not val_str or val_str in ["nan", "0", "-", "none", ""]: return False
    # Look for any digit to confirm a timestamp or data entry
    return bool(re.search(r'\d', val_str))

def calculate_metrics(row, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles, last_st, last_time, current_lap = 0.0, "Start", "6:00 AM", 1
    
    # Sequential Loop Check: Runner must have data in the current lap to be considered
    for lap in range(1, max_loops + 1):
        found_in_lap = False
        for i in range(4):
            col_idx = STATION_MAP.get((lap, i))
            if col_idx is not None and col_idx < len(row):
                val = str(row.iloc[col_idx]).strip()
                if is_valid_time(val):
                    dist = ((lap - 1) * loop_dist) + m_list[i]
                    max_miles, last_st, last_time, current_lap = dist, STATION_NAMES[i], val, lap
                    found_in_lap = True
        
        # If no data found for this entire lap, stop checking future laps
        if not found_in_lap:
            break

    if max_miles == 0:
        return "On Course", 0.0, STATION_NAMES[0], "---", 0.1
    
    elapsed = (now - START_TIME).total_seconds() / 3600
    speed = max_miles / elapsed if elapsed > 0 else 0
    
    # Next station prediction
    curr_idx = STATION_NAMES.index(last_st)
    next_idx = (curr_idx + 1) % 4
    next_st = STATION_NAMES[next_idx]
    l_idx = current_lap + 1 if (next_idx == 0 and curr_idx == 3) else current_lap
    
    next_dist = ((l_idx - 1) * loop_dist) + m_list[next_idx]
    
    expected = "---"
    if speed > 0 and max_miles < (max_loops * loop_dist):
        eta_delta = (next_dist - max_miles) / speed
        expected = (now + datetime.timedelta(hours=eta_delta)).strftime("%-I:%M %p")

    status = f"<div class='status-box'>{last_st}<br><span class='time-sub'>{last_time}</span></div>"
    if max_miles >= (max_loops * loop_dist):
        status = "<b>FINISHED!</b>"
    
    return status, max_miles, next_st, expected, max_miles

# 3. Data Loader
@st.cache_data(ttl=0)
def load_data(buster):
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={buster}"
    try:
        res = requests.get(url, timeout=10)
        # Load raw to maintain exact column alignment
        return pd.read_csv(io.StringIO(res.text), header=None, dtype=str)
    except: return None

# 4. Main App
if 'buster' not in st.session_state: 
    st.session_state['buster'] = int(time.time())

raw_df = load_data(st.session_state['buster'])

if raw_df is not None:
    st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live</h1>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns([3, 1])
    with col_a:
        view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
    with col_b:
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.session_state['buster'] = int(time.time())
            st.rerun()

    results = []
    # Starting at Row 3 to bypass title/header noise
    for i in range(3, len(raw_df)):
        row = raw_df.iloc[i]
        try:
            name = str(row.iloc[0]).strip()
            bib_str = str(row.iloc[1]).strip()
            
            # Skip empty rows or rows without a proper Bib
            if not bib_str.isdigit() or not name or name.lower() == "nan": 
                continue
            
            bib = int(bib_str)
            is_relay = 400 <= bib < 500
            
            if (view_mode == "Relay") == is_relay:
                status, miles, n_st, n_time, s_val = calculate_metrics(row, view_mode)
                results.append({
                    "Pos": 0, "Name": name, "Bib": bib, 
                    "Last Seen": status, "Miles": miles, 
                    "Next": n_st, "Expected": n_time, 
                    "sort_val": s_val
                })
        except: continue

    if results:
        final_df = pd.DataFrame(results).sort_values(by=['sort_val', 'Bib'], ascending=[False, True])
        final_df['Pos'] = range(1, len(final_df) + 1)
        st.write(final_df.drop(columns=['sort_val']).to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No data found. Ensure the Google Sheet is published and runners have Bibs/Names.")
