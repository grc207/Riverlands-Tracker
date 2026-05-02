import streamlit as st
import pandas as pd
import datetime
import time
import requests
import io

# 1. Setup & Styling
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

# 2. Timing
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) 
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

# 3. Position Logic
STATION_NAMES = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
MILES_100 = [4.5, 13.0, 20.5, 25.0]
MILES_RELAY = [3.5, 10.5, 16.5, 20.0]

def calculate_metrics_positional(row, bib_idx, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    max_miles, last_st, last_time, current_lap = 0.0, "", "", 1
    
    for lap in range(1, max_loops + 1):
        start_search_idx = (bib_idx + 1) + ((lap - 1) * 5)
        for i in range(4):
            col_idx = start_search_idx + i
            if col_idx < len(row):
                val = str(row.iloc[col_idx]).strip()
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

# 4. The "Invincible" Loader
@st.cache_data(ttl=10)
def load_data(mode, query=""):
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={int(time.time())}"
    try:
        # Step A: Get raw text via requests to avoid Pandas URL parsing issues
        response = requests.get(url)
        response.encoding = 'utf-8'
        raw_csv_text = response.text
        
        # Step B: Load without header inference or type checking
        df_raw = pd.read_csv(
            io.StringIO(raw_csv_text),
            skiprows=2,
            header=None,
            dtype=str,
            na_filter=False,  # This is the key to stopping the 'str' error
            keep_default_na=False
        )

        headers = df_raw.iloc[0].tolist()
        bib_idx = next((i for i, h in enumerate(headers) if h and "bib" in str(h).lower()), 1)
        name_idx = next((i for i, h in enumerate(headers) if h and ("team" in str(h).lower() or "runner" in str(h).lower())), 0)

        df = df_raw.iloc[1:].copy()
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
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# 5. UI
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
    st.info("Loading live data...")

time.sleep(15)
st.rerun()
