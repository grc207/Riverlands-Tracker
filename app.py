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

# 2. Timing Logic (UTC to EDT)
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4)

START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
RACE_LIMIT_HOURS = 32

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

# 3. Positional Search Logic
STATIONS = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
MILES_100 = [4.5, 13.0, 20.5, 25.0]
MILES_RELAY = [3.5, 10.5, 16.5, 20.0]

def calculate_metrics_positional(row, bib_idx, mode):
    m_list = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    last_st, last_time, current_lap = "", "", 1
    
    for lap in range(1, max_loops + 1):
        # Anchor to the FIRST bib column, then jump blocks of 5
        start_search = (bib_idx + 1) + ((lap - 1) * 5)
        
        for i in range(4):
            col_idx = start_search + i
            if col_idx < len(row):
                val = str(row.iloc[col_idx]).strip()
                if ":" in val:
                    dist = ((lap - 1) * loop_dist) + m_list[i]
                    if dist >= max_miles:
                        max_miles, last_st, last_time, current_lap = dist, STATIONS[i], val, lap

    if max_miles == 0: 
        return "On Course", 0.0, "---", 0.0, STATIONS[0], 1, 0.1
    if max_miles >= (max_loops * loop_dist): 
        return "<b>FINISHED!</b>", max_miles, "---", 0.0, "---", max_loops, 999

    speed = round(max_miles / ((now - START_TIME).total_seconds() / 3600), 1) if (now > START_TIME) else 0.0
    next_st = STATIONS[(STATIONS.index(last_st) + 1) % 4]
    return f"<div class='status-box'>{last_st}<br><span class='time-sub'>{last_time}</span></div>", max_miles, last_time, speed, next_st, current_lap, max_miles

# 4. Data Loading & Dynamic Header Mapping
@st.cache_data(ttl=15)
def load_data(mode, query=""):
    t_stamp = int(time.time())
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={t_stamp}"
    
    try:
        raw_df = pd.read_csv(url, header=None, dtype=str).fillna("")
        
        # Find the row containing "Bib"
        header_row_idx = 0
        for i, row in raw_df.iterrows():
            if any("bib" in str(cell).lower() for cell in row):
                header_row_idx = i
                break
        
        # Set headers and data
        header_labels = [str(c).strip() for c in raw_df.iloc[header_row_idx]]
        df = raw_df.iloc[header_row_idx+1:].copy()
        df.columns = header_labels
        
        # FIND THE FIRST BIB COLUMN ONLY
        bib_idx = -1
        for i, col_name in enumerate(header_labels):
            if "bib" in col_name.lower():
                bib_idx = i
                break # Stop at the first one found
        
        if bib_idx == -1:
            st.error("Error: Could not find any column named 'Bib'.")
            return pd.DataFrame()
            
        name_idx = bib_idx - 1 
        
        # Convert ONLY that specific column to numeric
        # This prevents the "arg must be a list" error
        df['_bib_clean'] = pd.to_numeric(df.iloc[:, bib_idx], errors='coerce')
        df = df.dropna(subset=['_bib_clean'])
        
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
search_input = st.text_input("🔍 Search Name:")

if st.button("🔄 Force Refresh Data"):
    st.cache_data.clear()
    st.rerun()

data_output = load_data(view_mode, search_input)

if not data_output.empty:
    st.write(data_output.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No active runners found or currently loading...")

time.sleep(30)
st.rerun()
