import streamlit as st
import pandas as pd
import datetime

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Live Leaderboard", layout="wide")

# 2. Race Constants & Timing
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) # Adjust for local time

STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}
STATION_ORDER = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]

def calculate_metrics(row, mode):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    last_station = ""
    last_time_str = ""
    current_loop = 1
    
    # 1. Parse timestamps to find progress
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
                    last_time_str = val_str
                    current_loop = lap

    # 2. Logic for Pre-Race vs. Active
    if now < START_TIME:
        return "Race Starts May 2nd @ 6am", 0.0, "00:00", "0.0", "Middle out", 1
    
    if max_miles == 0:
        return "On Course", 0.0, "---", "0.0", "Middle out", 1

    # 3. Handle Finishing
    if max_miles >= (max_loops * loop_dist):
        return "<b>FINISHED!</b>", max_miles, "---", "---", "---", max_loops

    # 4. Elapsed Time & Speed
    elapsed_str = "---"
    speed = "0.0"
    try:
        # Simple string-based elapsed time if timestamps are TOD
        elapsed_str = last_time_str 
        # Speed logic: total miles / hours since 6am (simplified for now)
        hours_since_start = (now - START_TIME).total_seconds() / 3600
        if hours_since_start > 0:
            speed = round(max_miles / hours_since_start, 1)
    except: pass

    # 5. Expected & Pacing Logic
    # 100 milers: +5% per loop after Loop 1. Relay: +10% per loop.
    next_idx = (STATION_ORDER.index(last_station) + 1) % len(STATION_ORDER)
    next_st = STATION_ORDER[next_idx]
    
    status_html = f"{last_station}<br><small>{last_time_str}</small>"
    
    return status_html, max_miles, elapsed_str, speed, next_st, current_loop

@st.cache_data(ttl=15)
def load_data(mode, query=""):
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    try:
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
            status, miles, elapsed, speed, expected, loop = calculate_metrics(row, mode)
            results.append({
                "Pos": 0,
                "Team/Runner": row[name_col],
                "Bib": str(int(row['_bib_num'])),
                "Status": status,
                "Total Miles": miles,
                "Elapsed Time": elapsed,
                "Speed": f"{speed} mph",
                "Expected": expected,
                "Loop": loop
            })
        
        if not results: return pd.DataFrame()
        
        # Live Sorting: Miles (Desc), then Bib (Asc) as a secondary
        full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'Bib'], ascending=[False, True])
        
        # Assign Position
        full_df['Pos'] = range(1, len(full_df) + 1)
        
        return full_df
        
    except Exception as e:
        st.error(f"Syncing Error: {e}")
        return pd.DataFrame()

# 4. UI Layout
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try: st.image("logo.jpg", use_container_width=True)
    except: st.write("*(Logo: logo.jpg)*")

view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search = st.text_input("🔍 Search Name:")

if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

data = load_data(view_mode, search)

if not data.empty:
    st.markdown("""<style>
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th { background-color: #f2f2f2; padding: 12px; border-bottom: 2px solid #333; }
        td { padding: 12px; border-bottom: 1px solid #ddd; text-align: center !important; }
        td:nth-child(2) { text-align: left !important; font-weight: bold; }
    </style>""", unsafe_allow_html=True)
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("Waiting for data...")
