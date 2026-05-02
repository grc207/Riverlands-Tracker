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

# 3. Data Processing Logic
STATION_NAMES = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
MILES_100 = [4.5, 13.0, 20.5, 25.0]
MILES_RELAY = [3.5, 10.5, 16.5, 20.0]

def calculate_metrics_positional(row, bib_idx, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    last_st = ""
    last_time = ""
    current_lap = 1
    
    # SCANNING POSITIONS: 
    # Start looking 1 column to the right of the first Bib column
    # Each 'lap block' is 5 columns (4 stations + 1 spacer/bib)
    for lap in range(1, max_loops + 1):
        start_search_idx = (bib_idx + 1) + ((lap - 1) * 5)
        
        for i in range(4): # Check the 4 station slots in this lap block
            col_idx = start_search_idx + i
            if col_idx < len(row):
                val = str(row.iloc[col_idx]).strip()
                if ":" in val: # If it has a colon, it's a time
                    dist = ((lap - 1) * loop_dist) + m_list[i]
                    if dist >= max_miles:
                        max_miles = dist
                        last_st = STATION_NAMES[i]
                        last_time = val
                        current_lap = lap

    if max_miles == 0:
        return "On Course", 0.0, "---", 0.0, STATION_NAMES[0], 1, 0.1
    
    if max_miles >= (max_loops * loop_dist):
        return "<b>FINISHED!</b>", max_miles, "---", 0.0, "---", max_loops, 999

    speed = round(max_miles / ((now - START_TIME).total_seconds() / 3600), 1) if (now > START_TIME) else 0.0
    next_idx = (STATION_NAMES.index(last_st) + 1) % 4
    next_st = STATION_NAMES[next_idx]
    
    status = f"<div class='status-box'>{last_st}<br><span class='time-sub'>{last_time}</span></div>"
    return status, max_miles, last_time, speed, next_st, current_lap, max_miles

# 4. Data Loading
@st.cache_data(ttl=10)
def load_data(mode, query=""):
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={int(time.time())}"
    try:
        # Load raw data with no headers first to find the index of "Bib"
        df_raw = pd.read_csv(url, skiprows=2, header=None, dtype=str).fillna("")
        
        # Determine which column index is the "Bib" column
        # We look at the first row (which was row 3 of the original sheet)
        headers = df_raw.iloc[0].tolist()
        bib_idx = -1
        name_idx = -1
        
        for i, h in enumerate(headers):
            if "bib" in str(h).lower():
                bib_idx = i
            if "team" in str(h).lower() or "runner" in str(h).lower():
                name_idx = i
        
        if bib_idx == -1: bib_idx = 1 # Fallback to common index
        if name_idx == -1: name_idx = 0 # Fallback to common index

        # Drop the header row from the data
        df = df_raw.iloc[1:].copy()
        
        # Filter by Bib
        df['_bib_num'] = pd.to_numeric(df.iloc[:, bib_idx], errors='coerce')
        df = df.dropna(subset=['_bib_num'])
        
        is_relay = (df['_bib_num'] >= 400) & (df['_bib_num'] < 500)
        active_df = df[is_relay].copy() if mode == "Relay" else df[~is_relay].copy()
        
        if query:
            active_df = active_df[active_df.iloc[:, name_idx].str.contains(query, case=False, na=False)]
            
        results = []
        for _, row in active_df.iterrows():
            status, miles, elapsed, speed, expected, loop, sort_val = calculate_metrics_positional(row, bib_idx, mode)
            results.append({
                "Pos": "", 
                "Team/Runner": row.iloc[name_idx], 
                "Bib": str(int(row['_bib_num'])),
                "Status": status, 
                "Miles": miles, 
                "Speed": f"{speed} mph", 
                "Next": expected, 
                "Loop": loop, 
                "sort_val": sort_val
            })
            
        if not results: return pd.DataFrame()
        
        full_df = pd.DataFrame(results).sort_values(by=['sort_val', 'Bib'], ascending=[False, True])
        moving = full_df['sort_val'] > 0.1
        if moving.any():
            full_df.loc[moving, 'Pos'] = range(1, moving.sum() + 1)
            
        return full_df.drop(columns=['sort_val'])
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# 5. UI
st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)
if now > START_TIME:
    st.subheader(f"⏱️ Race Clock: {format_delta_hhh(now - START_TIME)}")

view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search = st.text_input("🔍 Search Name:")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

data = load_data(view_mode, search)

if not data.empty:
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("Loading live data...")

time.sleep(15)
st.rerun()
