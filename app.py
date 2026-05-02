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

# 3. Positional Logic: Reading Left-to-Right from Bib
STATION_NAMES = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
MILES_100 = [4.5, 13.0, 20.5, 25.0]
MILES_RELAY = [3.5, 10.5, 16.5, 20.0]

def calculate_metrics_positional(row, bib_idx, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    last_st, last_time, current_lap = "", "", 1
    
    # logic: Start at Bib index and scan rightward
    for lap in range(1, max_loops + 1):
        # Calculate the starting column for this specific lap block
        # (Assuming 4 timing stations + 1 gap column per lap)
        start_search_idx = (bib_idx + 1) + ((lap - 1) * 5)
        
        for i in range(4):
            col_idx = start_search_idx + i
            if col_idx < len(row):
                val = str(row.iloc[col_idx]).strip()
                # If cell has a colon, it's a time. Update to the furthest right time found.
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

# 4. Safe Data Loading
@st.cache_data(ttl=10)
def load_data(mode, query=""):
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    try:
        # Load everything as 'object' (raw text) to prevent the error in IMG_4608.jpeg
        df_raw = pd.read_csv(url, skiprows=2, header=None, dtype=object).fillna("")
        
        # Identify Bib and Name indices from the first row of visible data
        header_row = df_raw.iloc[0].astype(str).tolist()
        bib_idx = next((i for i, h in enumerate(header_row) if "bib" in h.lower()), 1)
        name_idx = next((i for i, h in enumerate(header_row) if "runner" in h.lower() or "team" in h.lower()), 0)

        # Process data rows
        df = df_raw.iloc[1:].copy()
        dfI encountered an error doing what you asked. Could you try again?
