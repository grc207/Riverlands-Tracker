import streamlit as st
import pandas as pd
import datetime
import time

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

# 2. Timing Logic (EDT)
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4)

START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
RACE_LIMIT_HOURS = 32

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

# 3. Data Processing Logic
STATIONS = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
MILES_100 = [4.5, 13.0, 20.5, 25.0]
MILES_RELAY = [3.5, 10.5, 16.5, 20.0]

def calculate_metrics_positional(row, bib_idx, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    last_st, last_time, current_lap = "", "", 1
    
    # Position logic based on IMG_4604.jpeg: 4 stations + 1 spacer/repeated bib = block of 5
    for lap in range(1, max_loops + 1):
        # We jump 5 columns for every lap block
        start_search = (bib_idx + 1) + ((lap - 1) * 5)
        for i in range(4):
            col_idx = start_search + i
            if col_idx < len(row):
                val = str(row.iloc[col_idx]).strip()
                # If cell contains a colon, we treat it as valid time data
                if ":" in val:
                    dist = ((lap - 1) * loop_dist) + m_list[i]
                    if dist >= max_miles:
                        max_miles, last_st, last_time, current_lap = dist, STATIONS[i], val, lap

    # Status formatting
    if max_miles == 0: 
        return "On Course", 0.0, "---", 0.0, STATIONS[0], 1, 0.1
    if max_miles >= (max_loops * loop_dist): 
        return "<b>FINISHED!</b>", max_miles, "---", 0.0, "---", max_loops, 999

    # Speed calculation based on time since race start
    speed = round(max_miles / ((now - START_TIME).total_seconds() / 3600), 1) if (now > START_TIME) else 0.0
    next_st = STATIONS[(STATIONS.index(last_st) + 1) % 4]
    return f"<div class='status-box'>{last_st}<br><span class='time-sub'>{last_time}</span></div>", max_miles, last_time, speed, next_st, current_lap, max_miles

# 4. Data Loading - Surgical Search
@st.cache_data(ttl=10)
def load_data(mode, query=""):
    # Force fresh data by appending a timestamp to URL
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={int(time.time())}"
    
    try:
        # Step 1: Read skipping the first 2 rows (merged cells like "Lap 1")
        df = pd.read_csv(url, skiprows=2, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        
        # Step 2: Find the FIRST Bib column (the anchor)
        bib_idx = -1
        for i, col in enumerate(df.columns):
            if "bib" in col.lower():
                bib_idx = i
                break
        
        # Step 3: Find the Name column to the LEFT of the Bib
        name_idx = -1
        # Scan specifically for headers containing 'name', 'team', or 'runner'
        for i in range(bib_idx - 1, -1, -1):
            if any(word in df.columns[i].lower() for word in ["name", "team", "runner"]):
                name_idx = i
                break
        if name_idx == -1: name_idx = max(0, bib_idx - 1)

        if bib_idx == -1:
            st.error("Bib column not found. Check spreadsheet headers.")
            return pd.DataFrame()

        # Step 4: Strict Numeric Conversion
        # Targeting the series directly via iloc to avoid duplicate header errors (IMG_4606.jpeg)
        df['_bib_clean'] = pd.to_numeric(df.iloc[:, bib_idx], errors='coerce')
        df = df.dropna(subset=['_bib_clean'])
        
        # Step 5: Category Filtering (Relay = 400 range)
        is_relay = (df['_bib_clean'] >= 400) & (df['_bib_clean'] < 500)
        active_df = df[is_relay].copy() if mode == "Relay" else df[~is_relay].copy()
        
        if query:
            active_df = active_df[active_df.iloc[:, name_idx].str.contains(query, case=False, na=False)]
            
        results = []
        for _, row in active_df.iterrows():
            status, miles, elapsed, speed, expected, lap, sort_val = calculate_metrics_positional(row, bib_idx, mode)
            results.append({
                "Pos": "", 
                "Team/Runner": row.iloc[name_idx], 
                "Bib": str(int(row['_bib_clean'])),
                "Status": status, "Miles": miles, "Speed": f"{speed} mph", 
                "Next": expected, "Loop": lap, "sort_val": sort_val
            })
            
        if not results: return pd.DataFrame()

        # Sort by total miles covered, then bib number
        final_df = pd.DataFrame(results).sort_values(by=['sort_val', 'Bib'], ascending=[False, True])
        moving = final_df['sort_val'] > 0.1
        if moving.any(): final_df.loc[moving, 'Pos'] = range(1, moving.sum() + 1)
            
        return final_df.drop(columns=['sort_val'])
        
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# 5. UI Layout
st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)

if now > START_TIME:
    st.subheader(f"⏱️ Race Clock: {format_delta_hhh(now - START_TIME)}")

view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search_query = st.text_input("🔍 Search Name:")

if st.button("🔄 Force Refresh"):
    st.cache_data.clear()
    st.rerun()

data = load_data(view_mode, search_query)

if not data.empty:
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("Loading live data from source...")

# Auto-refresh rerun
time.sleep(20)
st.rerun()
