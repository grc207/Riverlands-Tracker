import streamlit as st
import pandas as pd
import datetime
from streamlit_autorefresh import st_autorefresh

# 1. Auto-Refresh Setup (Every 30 seconds)
st_autorefresh(interval=30 * 1000, key="datarefresh")

# 2. Page Configuration & CSS for Centering
st.set_page_config(page_title="Riverlands 100 Live Leaderboard", layout="wide")

st.markdown("""
    <style>
    /* Center all table headers and cells */
    th { text-align: center !important; background-color: #f2f2f2; padding: 12px; }
    td { text-align: center !important; padding: 12px; border-bottom: 1px solid #ddd; }
    /* Keep names left-aligned for readability */
    td:nth-child(2) { text-align: left !important; font-weight: bold; min-width: 180px; }
    </style>
    """, unsafe_allow_html=True)

# 3. Time Logic
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) # Eastern Time Adjustment

# 4. Station & Pacing Data
STATION_ORDER = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

def calculate_metrics(row, mode):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    last_station = ""
    last_time_val = None
    current_loop = 1
    
    # Identify progress and last known time
    for col_name, val in row.items():
        val_str = str(val).strip()
        if ":" in val_str:
            parts = col_name.split('.')
            base = parts[0].strip()
            if base in m_map:
                lap = int(parts[-1]) + 1 if (len(parts) > 1 and parts[-1].isdigit()) else 1
                dist = ((lap - 1) * loop_dist) + m_map[base]
                
                if dist >= max_miles:
                    max_miles = dist
                    last_station = base
                    last_time_val = val_str
                    current_loop = lap

    # Status Logic
    if now < START_TIME:
        return "Race Starts May 2nd @ 6am", 0.0, "00:00", "0.0", "Middle out", 1, 999999
    
    if max_miles == 0:
        return "On Course", 0.0, "---", "0.0", "Middle out", 1, 888888

    if max_miles >= (max_loops * loop_dist):
        return "<b>FINISHED!</b>", max_miles, "---", "---", "---", max_loops, 0

    # Elapsed Time & Speed (MPH)
    speed_val = 0.0
    elapsed_str = last_time_val
    try:
        hours_since_start = (now - START_TIME).total_seconds() / 3600
        if hours_since_start > 0:
            speed_val = round(max_miles / hours_since_start, 1)
    except: pass

    # Expected Arrival Calculation
    # Relay +10% per loop; 100 Miler +5% per loop after Loop 1
    pacing_factor = 1.10 if mode == "Relay" else (1.0 + (0.05 * (current_loop - 1)))
    next_idx = (STATION_ORDER.index(last_station) + 1) % len(STATION_ORDER)
    next_st = STATION_ORDER[next_idx]
    
    status_html = f"{last_station}<br><small>{last_time_val}</small>"
    
    # Sort key: Miles (descending) and time (if we had arrival timestamps as objects)
    sort_key = max_miles 
    
    return status_html, max_miles, elapsed_str, speed_val, next_st, current_loop, sort_key

@st.cache_data(ttl=15)
def load_data(mode, query=""):
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    try:
        # Based on image_11e619.png, skip the first 2 rows of merged headers
        df = pd.read_csv(url, skiprows=2, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        
        name_col = next((c for c in df.columns if "Team/Runner" in c), df.columns[0])
        bib_col = next((c for c in df.columns if "Bib" in c), df.columns[1])

        df['_bib_num'] = pd.to_numeric(df[bib_col], errors='coerce')
        df = df.dropna(subset=['_bib_num'])
        
        is_relay = (df['_bib_num'] >= 400) & (df['_bib_num'] < 500)
        active_df = df[is_relay].copy() if mode == "Relay" else df[~is_relay].copy()
            
        if query:
            active_df = active_df[active_df[name_col].str.contains(query, case=False, na=False)]
        
        results = []
        for _, row in active_df.iterrows():
            status, miles, elapsed, speed, expected, loop, sort_val = calculate_metrics(row, mode)
            results.append({
                "Pos": 0,
                "Team/Runner": row[name_col],
                "Bib": str(int(row['_bib_num'])),
                "Status": status,
                "Total Miles": miles,
                "Elapsed Time": elapsed,
                "Speed": f"{speed} mph",
                "Expected": expected,
                "Loop": loop,
                "sort_val": sort_val
            })
        
        if not results: return pd.DataFrame()
        
        # Sort by furthest distance (descending)
        full_df = pd.DataFrame(results).sort_values(by=['sort_val', 'Bib'], ascending=[False, True])
        
        # Position Assignment
        full_df['Pos'] = range(1, len(full_df) + 1)
        
        return full_df.drop(columns=['sort_val'])
        
    except Exception as e:
        st.error(f"Syncing Error: {e}")
        return pd.DataFrame()

# 5. UI Implementation
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try: st.image("logo.jpg", use_container_width=True)
    except: st.write("### RIVERLANDS 100")

view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search = st.text_input("🔍 Search Name:")

data = load_data(view_mode, search)

if not data.empty:
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("Loading participants...")
