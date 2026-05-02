import streamlit as st
import pandas as pd
import datetime

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

# 2. Timing & Clock Logic
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) # UTC to EDT

START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
RACE_LIMIT_HOURS = 32

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

# 3. Logo, Title, and Disclaimer
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try: 
        st.image("logo.jpg", use_container_width=True)
    except: 
        st.markdown("<h2 style='text-align: center;'>RIVERLANDS 100</h2>", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)

# Display the Clock
if now < START_TIME:
    st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
    st.write("**Hours until Race Day!**")
else:
    elapsed_diff = now - START_TIME
    display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
    st.subheader(f"⏱️ {format_delta_hhh(display_elapsed)}")
    st.write("**Elapsed Race Time**")

st.info("**Disclaimer:** This is an independent project and is not maintained by the race director. "
        "All information may not be timely or accurate and should NOT be accepted as official!\n\n"
        "Some updates may take a few minutes to refresh.")

# 4. Data Processing Logic
STATION_ORDER = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

def calculate_metrics(row, mode):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    max_miles = 0.0
    last_station = ""
    last_time_str = ""
    current_loop = 1
    
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

    if now < START_TIME:
        return "Race Starts May 2nd @ 6am", 0.0, "00:00", "0.0", "Middle out", 1, 0
    
    if max_miles == 0:
        return "On Course", 0.0, "---", "0.0", "Middle out", 1, 0.1

    if max_miles >= (max_loops * loop_dist):
        return "<b>FINISHED!</b>", max_miles, "---", "---", "---", max_loops, 999

    speed_mph = 0.0
    hours_elapsed = (now - START_TIME).total_seconds() / 3600
    if hours_elapsed > 0:
        speed_mph = round(max_miles / hours_elapsed, 1)

    next_idx = (STATION_ORDER.index(last_station) + 1) % len(STATION_ORDER)
    next_st = STATION_ORDER[next_idx]
    
    status_html = f"<div class='status-box'>{last_station}<br><span class='time-sub'>{last_time_str}</span></div>"
    return status_html, max_miles, last_time_str, speed_mph, next_st, current_loop, max_miles

@st.cache_data(ttl=10)
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
            status, miles, elapsed, speed, expected, loop, sort_val = calculate_metrics(row, mode)
            results.append({
                "Pos": "", "Team/Runner": row[name_col], "Bib": str(int(row['_bib_num'])),
                "Status": status, "Total Miles": miles, "Elapsed Time": elapsed,
                "Speed": f"{speed} mph", "Expected": expected, "Loop": loop, "sort_val": sort_val
            })
        if not results: return pd.DataFrame()
        full_df = pd.DataFrame(results).sort_values(by=['sort_val', 'Bib'], ascending=[False, True])
        moving_mask = full_df['sort_val'] > 0.1
        if moving_mask.any():
            full_df.loc[moving_mask, 'Pos'] = range(1, moving_mask.sum() + 1)
        return full_df.drop(columns=['sort_val'])
    except Exception as e:
        st.error(f"Data Sync Error: {e}")
        return pd.DataFrame()

# 5. User Interface
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
