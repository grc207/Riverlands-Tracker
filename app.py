import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup & Centered Styling
st.set_page_config(page_title="Riverlands 100 Live Leaderboard", layout="wide")

st.markdown("""
    <style>
    th { text-align: center !important; background-color: #f2f2f2; vertical-align: middle !important; }
    td { text-align: center !important; vertical-align: middle !important; border-bottom: 1px solid #ddd; }
    td:nth-child(2) { text-align: left !important; font-weight: bold; min-width: 180px; }
    .status-box { line-height: 1.2; }
    .time-sub { font-size: 0.85em; color: #555; }
    </style>
    """, unsafe_allow_html=True)

# 2. Timing Logic
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) # UTC to EDT
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

# 3. Positional Data Processing Logic
STATION_NAMES = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
MILES_100 = [4.5, 13.0, 20.5, 25.0]
MILES_RELAY = [3.5, 10.5, 16.5, 20.0]

def calculate_metrics_positional(row, bib_idx, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    last_st, last_time, current_lap = "", "", 1
    
    # Read every cell to the right of the Bib column
    for lap in range(1, max_loops + 1):
        # Calculation assumes 5 columns per lap block (4 stations + 1 spacer)
        start_search_idx = (bib_idx + 1) + ((lap - 1) * 5)
        
        for i in range(4):
            col_idx = start_search_idx + i
            if col_idx < len(row):
                val = str(row.iloc[col_idx]).strip()
                # Identify a time value by the presence of a colon
                if ":" in val:
                    dist = ((lap - 1) * loop_dist) + m_list[i]
                    if dist >= max_miles:
                        max_miles, last_st, last_time, current_lap = dist, STATION_NAMES[i], val, lap

    if max_miles == 0:
        return "On Course", 0.0, "---", 0.0, STATION_NAMES[0], 1, 0.1
    
    if max_miles >= (max_loops * loop_dist):
        return "<b>FINISHED!</b>", max_miles, "---", 0.0, "---", max_loops, 999

    speed = round(max_miles / ((now - START_TIME).total_seconds() / 3600), 1) if (now > START_TIME) else 0.0
    next_st = STATION_NAMES[(STATION_NAMES.index(last_st) + 1) % 4]
    
    status = f"<div class='status-box'>{last_st}<br><span class='time-sub'>{last_time}</span></div>"
    return status, max_miles, last_time, speed, next_st, current_lap, max_miles

# 4. Hardened Data Loading Block
@st.cache_data(ttl=10)
def load_data(mode, query=""):
    # Using a timestamp t in the URL to bypass any stale Google cache
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={int(time.time())}"
    try:
        # Crucial Fix: dtype=object and low_memory=False prevents the IMG_4610.jpeg error
        df_raw = pd.read_csv(url, skiprows=2, header=None, dtype=object, low_memory=False).fillna("")
        
        # Identify indices for Name and Bib dynamically from the first row of data
        headers = df_raw.iloc[0].astype(str).tolist()
        bib_idx = next((i for i, h in enumerate(headers) if "bib" in h.lower()), 1)
        name_idx = next((i for i, h in enumerate(headers) if "runner" in h.lower() or "team" in h.lower()), 0)

        df = df_raw.iloc[1:].copy()
        df['_bib_num'] = pd.to_numeric(df.iloc[:, bib_idx], errors='coerce')
        df = df.dropna(subset=['_bib_num'])
        
        is_relay = (df['_bib_num'] >= 400) & (df['_bib_num'] < 500)
        active_df = df[is_relay].copy() if mode == "Relay" else df[~is_relay].copy()
        
        if query:
            active_df = active_df[active_df.iloc[:, name_idx].astype(str).str.contains(query, case=False)]
            
        results = []
        for _, row in active_df.iterrows():
            status, miles, elapsed, speed, expected, loop, sort_val = calculate_metrics_positional(row, bib_idx, mode)
            results.append({
                "Pos": "", "Team/Runner": row.iloc[name_idx], "Bib": str(int(row['_bib_num'])),
                "Status": status, "Miles": miles, "Speed": f"{speed} mph", 
                "Next": expected, "Loop": loop, "sort_val": sort_val
            })
            
        if not results: return pd.DataFrame()
        
        full_df = pd.DataFrame(results).sort_values(by=['sort_val', 'Bib'], ascending=[False, True])
        moving = full_df['sort_val'] > 0.1
        if moving.any():
            full_df.loc[moving, 'Pos'] = range(1, moving.sum() + 1)
            
        return full_df.drop(columns=['sort_val'])
    except Exception as e:
        # Captures the specific error text if the loader still fails
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# 5. User Interface
st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)

if now > START_TIME:
    st.subheader(f"⏱️ Race Clock: {format_delta_hhh(now - START_TIME)}")

view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search_input = st.text_input("🔍 Search Name:")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

data = load_data(view_mode, search_input)

if not data.empty:
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("Waiting for race data...")

# Auto-refresh every 15 seconds
time.sleep(15)
st.rerun()
