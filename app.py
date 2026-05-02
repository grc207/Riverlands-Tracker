import streamlit as st
import pandas as pd
import datetime
import requests
import io
import time

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
MILES_100 = [4.5, 13.0, 20.5, 25.0]
MILES_RELAY = [3.5, 10.5, 16.5, 20.0]

def calculate_metrics_dynamic(row, station_map, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles, last_st, last_time, current_lap = 0.0, "", "", 1
    
    for (lap, st_key), col_idx in station_map.items():
        if col_idx < len(row):
            val = str(row.iloc[col_idx]).strip()
            if val and val.lower() not in ["", "-", "nan", "none", "0"]:
                st_idx = STATION_KEYWORDS.index(st_key)
                dist = ((lap - 1) * loop_dist) + m_list[st_idx]
                if dist >= max_miles:
                    max_miles, last_st, last_time, current_lap = dist, st_key, val, lap

    if max_miles == 0:
        return "On Course", 0.0, STATION_KEYWORDS[0], "---", 0.1
    if max_miles >= (max_loops * loop_dist):
        return "<b>FINISHED!</b>", max_miles, "---", "---", 999
    
    elapsed_hours = (now - START_TIME).total_seconds() / 3600
    speed = max_miles / elapsed_hours if elapsed_hours > 0 else 0
    
    curr_idx = STATION_KEYWORDS.index(last_st)
    next_idx = (curr_idx + 1) % 4
    next_st = STATION_KEYWORDS[next_idx]
    
    next_dist = ((current_lap - 1) * loop_dist) + m_list[next_idx]
    if next_idx == 0 and curr_idx == 3:
        next_dist = (current_lap * loop_dist) + m_list[0]
    
    expected_str = "---"
    if speed > 0:
        hours_to_next = (next_dist - max_miles) / speed
        expected_str = (now + datetime.timedelta(hours=hours_to_next)).strftime("%-I:%M %p")

    display_time = last_time.split(" ")[-1] if " " in last_time else last_time
    status = f"<div class='status-box'>{last_st.title()}<br><span class='time-sub'>{display_time}</span></div>"
    
    return status, max_miles, next_st.title(), expected_str, max_miles

# 3. Data Loader
@st.cache_data(ttl=0)
def load_raw_data(buster):
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={buster}"
    try:
        response = requests.get(url, timeout=15)
        # Load everything as raw strings initially
        return pd.read_csv(io.StringIO(response.text), header=None, dtype=str)
    except:
        return None

# 4. Processing
if 'buster' not in st.session_state:
    st.session_state['buster'] = int(time.time())

df_all = load_raw_data(st.session_state['buster'])

if df_all is not None:
    # STEP 1: Find the header row (the one with 'Bib' or 'Name')
    header_row_idx = 0
    for idx, row in df_all.iterrows():
        row_str = " ".join(row.astype(str)).lower()
        if "bib" in row_str or "name" in row_str:
            header_row_idx = idx
            break
    
    headers = [str(h).lower().strip() for h in df_all.iloc[header_row_idx]]
    
    # STEP 2: Map columns based on keywords
    station_map = {}
    for lap in range(1, 6):
        for st_key in STATION_KEYWORDS:
            occ = 0
            for col_idx, h_text in enumerate(headers):
                if st_key in h_text:
                    occ += 1
                    if occ == lap:
                        station_map[(lap, st_key)] = col_idx
                        break

    # STEP 3: Clean up data rows
    df_runners = df_all.iloc[header_row_idx + 1:].copy()
    
    st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live</h1>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns([3, 1])
    with col_a:
        view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
    with col_b:
        if st.button("🔄 Refresh Data Now"):
            st.cache_data.clear()
            st.session_state['buster'] = int(time.time())
            st.rerun()

    results = []
    for _, row in df_runners.iterrows():
        try:
            name = str(row.iloc[0]).strip()
            bib_str = str(row.iloc[1]).strip()
            
            if not bib_str.isdigit() or name.lower() in ["nan", "name", ""]: continue
            
            bib = int(bib_str)
            is_relay = 400 <= bib < 500
            
            if (view_mode == "Relay" and is_relay) or (view_mode == "100 Miler" and not is_relay):
                status, miles, n_st, n_time, s_val = calculate_metrics_dynamic(row, station_map, view_mode)
                results.append({
                    "Pos": 0, "Name": name, "Bib": bib,
                    "Last Seen": status, "Miles": miles,
                    "Next": n_st, "Expected": n_time, "sort_val": s_val
                })
        except:
            continue

    if results:
        final_df = pd.DataFrame(results).sort_values(by=['sort_val', 'Bib'], ascending=[False, True])
        final_df['Pos'] = range(1, len(final_df) + 1)
        st.write(final_df.drop(columns=['sort_val']).to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.warning("Data sync in progress... please wait a moment and click refresh.")
