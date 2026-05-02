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

STATION_KEYWORDS = ["middle out", "conant rd", "middle back", "arrive s/f"]
STATION_DISPLAY = ["Middle Out", "Conant Rd", "Middle Back", "Arrive S/F"]

MILES_100 = [4.5, 13.0, 20.5, 25.0]
MILES_RELAY = [3.5, 10.5, 16.5, 20.0]

def is_valid_time(val):
    if not val or len(str(val)) < 3: return False
    return bool(re.search(r'\d+:\d+', str(val)))

def calculate_metrics(row, station_map, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles, last_st, last_time, current_lap = 0.0, "Start", "6:00 AM", 1
    
    # Sequential Loop Check: Must finish one lap before moving to next
    for lap in range(1, max_loops + 1):
        lap_found_any = False
        for i, key in enumerate(STATION_KEYWORDS):
            col_idx = station_map.get((lap, key))
            if col_idx is not None and col_idx < len(row):
                val = str(row.iloc[col_idx]).strip()
                if is_valid_time(val):
                    dist = ((lap - 1) * loop_dist) + m_list[i]
                    max_miles, last_st, last_time, current_lap = dist, STATION_DISPLAY[i], val, lap
                    lap_found_any = True
        
        if not lap_found_any:
            break

    if max_miles == 0:
        return "On Course", 0.0, STATION_DISPLAY[0], "---", 0.1
    
    elapsed_hours = (now - START_TIME).total_seconds() / 3600
    speed = max_miles / elapsed_hours if elapsed_hours > 0 else 0
    
    # Next station calculation
    try:
        curr_idx = STATION_DISPLAY.index(last_st)
        next_idx = (curr_idx + 1) % 4
        next_st = STATION_DISPLAY[next_idx]
        l_idx = current_lap + 1 if next_idx == 0 else current_lap
        next_dist = ((l_idx - 1) * loop_dist) + m_list[next_idx]
    except:
        next_st, next_dist = "Finish", max_miles

    expected_str = "---"
    if speed > 0 and max_miles < (max_loops * loop_dist):
        hours_to_next = (next_dist - max_miles) / speed
        expected_str = (now + datetime.timedelta(hours=hours_to_next)).strftime("%-I:%M %p")

    status = f"<div class='status-box'>{last_st}<br><span class='time-sub'>{last_time}</span></div>"
    if max_miles >= (max_loops * loop_dist): status = "<b>FINISHED!</b>"
    
    return status, max_miles, next_st, expected_str, max_miles

# 3. Data Loader
@st.cache_data(ttl=0)
def load_and_map_data(buster):
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={buster}"
    try:
        res = requests.get(url, timeout=10)
        full_df = pd.read_csv(io.StringIO(res.text), header=None, dtype=str)
        
        # Find the header row (the one with 'Bib')
        header_idx = 0
        for idx, row in full_df.iterrows():
            if "bib" in " ".join(row.astype(str)).lower():
                header_idx = idx
                break
        
        headers = [str(h).lower().strip() for h in full_df.iloc[header_idx]]
        
        # DYNAMIC SCAN: Map every station to its actual column
        station_map = {}
        for lap in range(1, 6):
            for key in STATION_KEYWORDS:
                count = 0
                for col_idx, h_text in enumerate(headers):
                    if key in h_text:
                        count += 1
                        if count == lap:
                            station_map[(lap, key)] = col_idx
                            break
                            
        return full_df.iloc[header_idx+1:], station_map
    except:
        return None, {}

# 4. App
if 'buster' not in st.session_state: st.session_state['buster'] = int(time.time())

df_runners, s_map = load_and_map_data(st.session_state['buster'])

if df_runners is not None:
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
    for _, row in df_runners.iterrows():
        try:
            name, bib_str = str(row.iloc[0]).strip(), str(row.iloc[1]).strip()
            if not bib_str.isdigit() or not name: continue
            
            bib = int(bib_str)
            is_relay = 400 <= bib < 500
            
            if (view_mode == "Relay" and is_relay) or (view_mode == "100 Miler" and not is_relay):
                status, miles, n_st, n_time, s_val = calculate_metrics(row, s_map, view_mode)
                results.append({"Pos": 0, "Name": name, "Bib": bib, "Last Seen": status, "Miles": miles, "Next": n_st, "Expected": n_time, "sort_val": s_val})
        except: continue

    if results:
        final_df = pd.DataFrame(results).sort_values(by=['sort_val', 'Bib'], ascending=[False, True])
        final_df['Pos'] = range(1, len(final_df) + 1)
        st.write(final_df.drop(columns=['sort_val']).to_html(escape=False, index=False), unsafe_allow_html=True)
