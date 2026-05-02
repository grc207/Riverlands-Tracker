import streamlit as st
import pandas as pd
import datetime

# 1. Setup & Centered Styling
st.set_page_config(page_title="Riverlands 100 Live Leaderboard", layout="wide")

st.markdown("""
    <style>
    /* Center headers and all cells */
    th { text-align: center !important; background-color: #f2f2f2; vertical-align: middle !important; }
    td { text-align: center !important; vertical-align: middle !important; border-bottom: 1px solid #ddd; }
    /* Names remain left-aligned for readability */
    td:nth-child(2) { text-align: left !important; font-weight: bold; min-width: 180px; }
    /* Status column formatting for the two-line time display */
    .status-box { line-height: 1.2; }
    .time-sub { font-size: 0.85em; color: #555; }
    </style>
    """, unsafe_allow_html=True)

# 2. Timing & Constants
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
# Current time check for "Race Starts" vs "On Course" logic
# Note: In the final version, this uses the real-time clock
now = datetime.datetime.now() 

STATION_ORDER = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

# 3. Core Flow Logic
def calculate_metrics(row, mode):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    last_station = ""
    last_time_str = ""
    current_loop = 1
    
    # Identify the furthest progress across all columns
    for col_name, val in row.items():
        val_str = str(val).strip()
        if ":" in val_str:
            parts = col_name.split('.')
            base = parts[0].strip()
            if base in m_map:
                # Loop detection via Pandas column suffix (.1, .2, etc)
                lap = int(parts[-1]) + 1 if (len(parts) > 1 and parts[-1].isdigit()) else 1
                dist = ((lap - 1) * loop_dist) + m_map[base]
                
                if dist >= max_miles:
                    max_miles = dist
                    last_station = base
                    last_time_str = val_str
                    current_loop = lap

    # STATUS & SORTING LOGIC
    # Before race start
    if now < START_TIME:
        return "Race Starts May 2nd @ 6am", 0.0, "00:00", "0.0", "Middle out", 1, 0
    
    # After 6am but no data yet
    if max_miles == 0:
        return "On Course", 0.0, "---", "0.0", "Middle out", 1, 0.1

    # Final Finish check
    if max_miles >= (max_loops * loop_dist):
        return "<b>FINISHED!</b>", max_miles, "---", "---", "---", max_loops, 999

    # SPEED & ELAPSED
    # Speed = Distance / (Current Time - 6:00 AM)
    speed_mph = 0.0
    hours_elapsed = (now - START_TIME).total_seconds() / 3600
    if hours_elapsed > 0:
        speed_mph = round(max_miles / hours_elapsed, 1)

    # EXPECTED NEXT STATION
    # If just arrived at S/F but not finished, next is Middle Out of next loop
    next_idx = (STATION_ORDER.index(last_station) + 1) % len(STATION_ORDER)
    next_st = STATION_ORDER[next_idx]
    
    # HTML formatted status for two-line display
    status_html = f"<div class='status-box'>{last_station}<br><span class='time-sub'>{last_time_str}</span></div>"
    
    # Sort value uses miles as primary, then bib as tie-break in load_data
    return status_html, max_miles, last_time_str, speed_mph, next_st, current_loop, max_miles

@st.cache_data(ttl=10) # Cache for 10 seconds to allow quick manual refreshes
def load_data(mode, query=""):
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    try:
        # Skips metadata rows based on image_11e619.png
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
        
        # PRIMARY SORT: Mileage (Highest first)
        full_df = pd.DataFrame(results).sort_values(by=['sort_val', 'Bib'], ascending=[False, True])
        
        # POSITION: Only assign rank to those who have started (sort_val > 0)
        full_df['Pos'] = ""
        moving_mask = full_df['sort_val'] > 0.1
        if moving_mask.any():
            full_df.loc[moving_mask, 'Pos'] = range(1, moving_mask.sum() + 1)
        
        return full_df.drop(columns=['sort_val'])
        
    except Exception as e:
        st.error(f"Data Sync Error: {e}")
        return pd.DataFrame()

# 4. User Interface
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try: st.image("logo.jpg", use_container_width=True)
    except: st.markdown("<h2 style='text-align: center;'>RIVERLANDS 100</h2>", unsafe_allow_html=True)

view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search = st.text_input("🔍 Search Name:")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

data = load_data(view_mode, search)

if not data.empty:
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No active participants found in this category.")
