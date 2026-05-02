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

# 2. Timing (UTC to EDT)
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4)

START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
RACE_LIMIT_HOURS = 32

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

# 3. Header & Clock
st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)

if now < START_TIME:
    st.subheader(f"⏱️ Countdown: {format_delta_hhh(START_TIME - now)}")
else:
    elapsed = min(now - START_TIME, datetime.timedelta(hours=RACE_LIMIT_HOURS))
    st.subheader(f"⏱️ Elapsed: {format_delta_hhh(elapsed)}")

# 4. Station Logic (Matches IMG_4604.jpeg exactly)
STATION_ORDER = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

def calculate_metrics(row, mode):
    m_map = MILES_100 if mode == "100 Miler" else MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    last_st, last_time, current_lap = "", "", 1
    
    # SCAN EVERY COLUMN: Avoids issues with "Middle out.1", "Middle out.2", etc.
    for col_name, val in row.items():
        val_str = str(val).strip()
        
        # Look for a time format (HH:MM)
        if ":" in val_str:
            col_clean = str(col_name).strip().lower()
            
            # Identify which station this column belongs to
            matched_st = next((s for s in m_map.keys() if s.lower() in col_clean), None)
            
            if matched_st:
                # Determine lap from Pandas suffix (e.g., .1, .2)
                parts = col_clean.split('.')
                lap = int(parts[-1]) + 1 if len(parts) > 1 and parts[-1].isdigit() else 1
                
                dist = ((lap - 1) * loop_dist) + m_map[matched_st]
                
                if dist >= max_miles:
                    max_miles, last_st, last_time, current_lap = dist, matched_st, val_str, lap

    if max_miles == 0: return "On Course", 0.0, "---", 0.0, "Middle out", 1, 0.1
    if max_miles >= (max_loops * loop_dist): return "<b>FINISHED!</b>", max_miles, "---", 0.0, "---", max_loops, 999

    speed = round(max_miles / ((now - START_TIME).total_seconds() / 3600), 1) if (now > START_TIME) else 0.0
    next_st = STATION_ORDER[(STATION_ORDER.index(last_st) + 1) % len(STATION_ORDER)]
    
    status = f"<div class='status-box'>{last_st}<br><span class='time-sub'>{last_time}</span></div>"
    return status, max_miles, last_time, speed, next_st, current_lap, max_miles

# 5. Data Loading with Cache Bypass
@st.cache_data(ttl=15)
def load_data(mode, query=""):
    # Force Google to refresh by adding a dynamic timestamp to the URL
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={int(time.time())}"
    
    try:
        # Use skiprows=2 to bypass the 'Lap 1' merged header in IMG_4604.jpeg
        df = pd.read_csv(url, skiprows=2, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        
        name_col = next((c for c in df.columns if "Team/Runner" in c), df.columns[0])
        bib_col = next((c for c in df.columns if "Bib" in c), df.columns[1])
        
        df['_bib'] = pd.to_numeric(df[bib_col], errors='coerce')
        df = df.dropna(subset=['_bib'])
        
        # Relay vs 100 Miler filter
        is_relay = (df['_bib'] >= 400) & (df['_bib'] < 500)
        active_df = df[is_relay].copy() if mode == "Relay" else df[~is_relay].copy()
        
        if query:
            active_df = active_df[active_df[name_col].str.contains(query, case=False, na=False)]
            
        results = []
        for _, row in active_df.iterrows():
            status, miles, elapsed, speed, expected, lap, sort_val = calculate_metrics(row, mode)
            results.append({
                "Pos": "", "Team/Runner": row[name_col], "Bib": str(int(row['_bib'])),
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

# 6. UI & Automatic Refresh
mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search = st.text_input("🔍 Search Name:")

if st.button("🔄 Force Data Refresh"):
    st.cache_data.clear()
    st.rerun()

data = load_data(mode, search)
if not data.empty:
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No data found. Check Bib numbers and Google Sheet publication.")

# Auto-rerun every 30 seconds
time.sleep(30)
st.rerun()
