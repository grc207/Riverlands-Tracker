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
    .disclaimer { font-size: 0.8em; color: #888; text-align: center; margin-top: 20px; }
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
            if col_idx is not None and col_idx < len(row):
                val = str(row.iloc[col_idx]).strip()
                if val and val not in ["", "-", "nan", "None", "0"]:
                    dist = ((lap - 1) * loop_dist) + m_list[i]
                    if dist >= max_miles:
                        max_miles, last_st, last_time, current_lap = dist, st_name, val, lap

    if max_miles == 0:
        return "On Course", 0.0, "---", "0.0", STATION_NAMES[0], "---", 0.1
    if max_miles >= (max_loops * loop_dist):
        return "<b>FINISHED!</b>", max_miles, last_time, "---", "---", "---", 999
    
    elapsed_hours = (now - START_TIME).total_seconds() / 3600
    speed = max_miles / elapsed_hours if elapsed_hours > 0 else 0
    
    curr_idx = STATION_NAMES.index(last_st)
    next_idx = (curr_idx + 1) % 4
    next_st = STATION_NAMES[next_idx]
    
    next_dist = ((current_lap - 1) * loop_dist) + m_list[next_idx]
    if next_idx == 0 and curr_idx == 3:
        next_dist = (current_lap * loop_dist) + m_list[0]
        
    miles_to_go = next_dist - max_miles
    expected_str = "---"
    if speed > 0:
        hours_to_next = miles_to_go / speed
        expected_dt = now + datetime.timedelta(hours=hours_to_next)
        expected_str = expected_dt.strftime("%-I:%M %p")

    display_time = last_time.split(" ")[-1] if " " in last_time else last_time
    status = f"<div class='status-box'>{last_st}<br><span class='time-sub'>{display_time}</span></div>"
    
    return status, max_miles, last_time, f"{speed:.1f}", next_st, expected_str, max_miles

# 3. Data Loader
@st.cache_data(ttl=0)
def load_raw_data(buster):
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={buster}"
    try:
        # Increased timeout for spotty connections
        response = requests.get(url, timeout=15)
        return pd.read_csv(io.StringIO(response.text), skiprows=2, header=None, dtype=str)
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")
        return None

# 4. Processing
# Initialize buster if not present
if 'buster' not in st.session_state:
    st.session_state['buster'] = int(time.time())

df_raw = load_raw_data(st.session_state['buster'])

if df_raw is not None:
    headers = [str(h).lower().strip() for h in df_raw.iloc[0].tolist()]
    
    # Station Mapping Logic
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
            name = str(row.iloc[0]).strip()
            bib_str = str(row.iloc[1]).strip() if len(row) > 1 else ""
            
            if not bib_str.isdigit() or not name: continue
            
            bib = int(bib_str)
            is_relay = 400 <= bib < 500
            
            if (view_mode == "Relay" and is_relay) or (view_mode == "100 Miler" and not is_relay):
                status, miles, l_time, speed, n_st, n_time, s_val = calculate_metrics_dynamic(row, station_map, view_mode)
                results.append({
                    "Pos": 0, "Name": name, "Bib": bib,
                    "Last Seen": status, "Miles": miles, "MPH": speed,
                    "Next Station": n_st, "Expected": n_time, "sort_val": s_val
                })
        except:
            continue # Skip individual row if it's broken

    if results:
        final_df = pd.DataFrame(results).sort_values(by=['sort_val', 'Bib'], ascending=[False, True])
        final_df['Pos'] = range(1, len(final_df) + 1)
        st.write(final_df.drop(columns=['sort_val']).to_html(escape=False, index=False), unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class='disclaimer'>
                <b>Data Current as of:</b> {now.strftime('%H:%M:%S')} EDT<br>
                Predictions are pace-based estimates.
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Waiting for data to populate for this category...")
