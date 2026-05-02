import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup & Logo
st.set_page_config(page_title="Riverlands 100 Live Leaderboard", layout="wide")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo.jpg", use_container_width=True)
    except:
        st.write("*(Logo Placeholder: logo.jpg)*")

st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)

# 2. Disclaimer
st.info("**Disclaimer:** This is an independent project and is not maintained by the race director.")

# 3. Timezone Logic (UTC to EDT)
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) 
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
RACE_LIMIT_HOURS = 32

if now < START_TIME:
    delta = START_TIME - now
    hours_total = delta.seconds // 3600 + delta.days * 24
    st.subheader(f"⏱️ {hours_total}h {(delta.seconds // 60) % 60:02d}m")
    st.write("**Countdown to Race Start**")
else:
    elapsed = min(now - START_TIME, datetime.timedelta(hours=RACE_LIMIT_HOURS))
    hours_total = elapsed.seconds // 3600 + elapsed.days * 24
    st.subheader(f"⏱️ {hours_total}h {(elapsed.seconds // 60) % 60:02d}m")
    st.write("**Elapsed Race Time**")

# 4. Processing Logic
STATIONS_100 = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

def get_status(row, mode, global_has_data):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    total_race_dist = 100.0
    
    if not global_has_data:
        return "Race starts May 2nd @ 6am", 0.0, "---", 999999, "---"

    max_miles, furthest_station = 0.0, ""
    for col_name, val in row.items():
        val_str = str(val).strip().lower()
        if ":" in val_str:
            base = col_name.split('.')[0].strip()
            if "Start/Finish" in base: base = "Arrive S/F"
            if base in m_map:
                try:
                    lap = int(col_name.split('.')[-1]) + 1 if "." in col_name else 1
                except: lap = 1
                dist = ((lap - 1) * loop_dist) + m_map[base]
                if dist >= max_miles:
                    max_miles, furthest_station = dist, base

    row_str = " ".join(map(str, row.values)).lower()
    if "dnf" in row_str: return "DNF", max_miles, "---", 999999, "---"
    if max_miles >= total_race_dist: return "Finished!", total_race_dist, "---", 0, "N/A"
    if max_miles == 0: return "Not Started", 0.0, "---", 999999, "<b>Middle out</b>"
    return f"<b>{furthest_station}</b>", max_miles, "In Progress", 500, "---"

@st.cache_data(ttl=30)
def load_data(mode, query=""):
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    try:
        # FORCE ALL DATA TO BE STRINGS IMMEDIATELY
        df = pd.read_csv(url, dtype=str, low_memory=False)
        
        # 1. Locate the Bib column
        bib_idx = None
        for i, col in enumerate(df.columns):
            if "Bib" in str(col):
                bib_idx = i
                break
        
        if bib_idx is None or bib_idx == 0:
            return pd.DataFrame()

        # 2. Identify Names/Teams as the cell directly to the left of Bib
        name_col_name = df.columns[bib_idx - 1]
        bib_col_name = df.columns[bib_idx]

        # 3. Create a numeric helper for filtering, but keep the original strings for display
        df['_bib_num'] = pd.to_numeric(df[bib_col_name], errors='coerce')
        df = df.dropna(subset=['_bib_num'])

        # 4. Filter by Relay vs 100 Miler
        is_relay = (df['_bib_num'] >= 400) & (df['_bib_num'] < 500)
        active_df = df[is_relay].copy() if mode == "Relay" else df[~is_relay].copy()

        # 5. UI Search
        if query:
            active_df = active_df[
                active_df[name_col_name].str.contains(query, case=False, na=False) | 
                active_df[bib_col_name].str.contains(query, na=False)
            ]

        # Check for colon (timing data)
        global_has_data = active_df.astype(str).apply(lambda x: x.str.contains(":")).any().any()

        results = []
        for _, row in active_df.iterrows():
            status, miles, r_time, s_sec, expected = get_status(row, mode, global_has_data)
            
            # Format display bib (removes .0 if it was parsed as float earlier)
            display_bib = str(int(row['_bib_num']))

            results.append({
                "Pos": 0, 
                "Team/Runner": str(row[name_col_name]), 
                "Bib": display_bib, 
                "Status": status, 
                "Total Miles": miles, 
                "Race Time": r_time, 
                "Expected": expected, 
                "SortSec": s_sec
            })

        if not results: return pd.DataFrame()
        
        full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'SortSec'], ascending=[False, True])
        mask = (full_df['Total Miles'] > 0) & (~full_df['Status'].str.contains("Not Started|Race"))
        full_df.loc[mask, 'Pos'] = range(1, mask.sum() + 1)
        full_df.loc[~mask, 'Pos'] = ""
        
        return full_df.drop(columns=['SortSec'])
    except Exception as e:
        st.error(f"Error connecting to data: {e}")
        return pd.DataFrame()

# 5. UI Rendering
view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search = st.text_input("🔍 Search Name or Bib:") if view_mode == "100 Miler" else ""

if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

data = load_data(view_mode, search)
if not data.empty:
    st.markdown("""<style>
        table { width: 100%; border-collapse: collapse; font-family: sans-serif; }
        th { background-color: #f2f2f2; padding: 12px; border: 1px solid #ddd; font-weight: bold; text-align: center !important; }
        td { padding: 12px; border: 1px solid #ddd; text-align: center !important; vertical-align: middle; }
        td:nth-child(2) { text-align: left !important; font-weight: 500; }
    </style>""", unsafe_allow_html=True)
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("Waiting for data sync or no participants found.")
