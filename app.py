import streamlit as st
import pandas as pd
import datetime
import time
import requests
import io

# 1. Setup & Styling
st.set_page_config(page_title="Riverlands 100 Live", layout="wide")

st.markdown("""
    <style>
    th { text-align: center !important; background-color: #f2f2f2; }
    td { text-align: center !important; border-bottom: 1px solid #ddd; }
    td:nth-child(2) { text-align: left !important; font-weight: bold; }
    .status-box { line-height: 1.2; font-weight: bold; color: #1e3a8a; }
    </style>
    """, unsafe_allow_html=True)

# 2. Timing & Constants
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) 
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)

STATION_NAMES = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
MILES_100 = [4.5, 13.0, 20.5, 25.0]
MILES_RELAY = [3.5, 10.5, 16.5, 20.0]

def calculate_metrics_dynamic(row, station_map, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles, last_st, last_time, current_lap = 0.0, "", "", 1
    
    for lap in range(1, max_loops + 1):
        for i, st_name in enumerate(STATION_NAMES):
            col_idx = station_map.get((lap, st_name.lower()))
            if col_idx is not None:
                val = str(row.iloc[col_idx]).strip()
                # Check for timestamp or numeric data
                if ":" in val or (len(val) > 4 and val.replace('.','').isdigit()):
                    dist = ((lap - 1) * loop_dist) + m_list[i]
                    if dist >= max_miles:
                        max_miles, last_st, last_time, current_lap = dist, st_name, val, lap

    if max_miles == 0:
        return "On Course", 0.0, "---", 0.0, STATION_NAMES[0], 1, 0.1
    if max_miles >= (max_loops * loop_dist):
        return "<b>FINISHED!</b>", max_miles, "---", 0.0, "---", max_loops, 999
    
    speed = round(max_miles / ((now - START_TIME).total_seconds() / 3600), 1) if (now > START_TIME) else 0.0
    next_idx = (STATION_NAMES.index(last_st) + 1) % 4
    next_st = STATION_NAMES[next_idx]
    status = f"<div class='status-box'>{last_st}<br><span style='font-size:0.8em; color:#555;'>{last_time}</span></div>"
    return status, max_miles, last_time, speed, next_st, current_lap, max_miles

# 3. Data Loader with URL Buster
@st.cache_data(ttl=0) # ttl=0 still encourages fresh fetches without full cache wipes
def load_raw_data(buster):
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={buster}"
    try:
        response = requests.get(url, timeout=5)
        # SKIPROWS=2 ensures we land on Row 3 for our headers
        return pd.read_csv(io.StringIO(response.text), skiprows=2, header=None, dtype=str)
    except:
        return None

# 4. Main Processing
df_raw = load_raw_data(int(time.time()))

if df_raw is not None:
    # Identify Headers from Row 3
    headers = [str(h).lower().strip() for h in df_raw.iloc[0].tolist()]
    
    # Map Stations sequentially, jumping over ghost columns like 9 & 10
    station_map = {}
    last_found = -1
    for lap in range(1, 6):
        for st_name in STATION_NAMES:
            for col_idx in range(last_found + 1, len(headers)):
                if st_name.lower() in headers[col_idx]:
                    station_map[(lap, st_name.lower())] = col_idx
                    last_found = col_idx
                    break

    df_runners = df_raw.iloc[1:].copy()
    view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
    
    results = []
    for _, row in df_runners.iterrows():
        bib_val = str(row.iloc[1]).strip() # Row index 1 is Column B (Bib)
        if not bib_val.isdigit(): continue
        
        bib = int(bib_val)
        is_relay = 400 <= bib < 500
        
        if (view_mode == "Relay" and is_relay) or (view_mode == "100 Miler" and not is_relay):
            status, miles, elapsed, speed, expected, loop, sort_val = calculate_metrics_dynamic(row, station_map, view_mode)
            results.append({
                "Pos": "", "Name": row.iloc[0], "Bib": bib,
                "Last Station": status, "Miles": miles, "Next": expected, 
                "Loop": loop, "sort_val": sort_val
            })

    if results:
        final_df = pd.DataFrame(results).sort_values(by=['sort_val', 'Bib'], ascending=[False, True])
        final_df['Pos'] = range(1, len(final_df) + 1)
        st.write(final_df.drop(columns=['sort_val']).to_html(escape=False, index=False), unsafe_allow_html=True)

# 5. Manual Refresh Button (The Only Place We Clear)
if st.button("🔄 Force Clear & Refresh"):
    st.cache_data.clear() # Clears stored data only when clicked
    st.rerun()

# 6. Smooth Auto-Heartbeat
time.sleep(20)
st.rerun()
