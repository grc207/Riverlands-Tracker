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
st.info("**Disclaimer:** This is an independent project and is not maintained by the race director. "
        "All information may not be timely or accurate.")

# 3. Timezone Logic
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) 
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
RACE_LIMIT_HOURS = 32

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

if now < START_TIME:
    st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
    st.write("**Countdown to Race Start**")
else:
    elapsed_diff = now - START_TIME
    display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
    st.subheader(f"⏱️ {format_delta_hhh(display_elapsed)}")
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

    max_miles, furthest_station, last_time_str = 0.0, "", ""
    # Only look for times in the row
    for col_name, val in row.items():
        val_str = str(val).strip().lower()
        if ":" in val_str:
            base_header = col_name.split('.')[0].strip()
            if "Start/Finish" in base_header: base_header = "Arrive S/F"
            if base_header in m_map:
                try:
                    # Detect lap from the .1, .2 suffix Google adds to duplicate headers
                    lap_num = int(col_name.split('.')[-1]) + 1 if "." in col_name else 1
                except: lap_num = 1
                calc_miles = ((lap_num - 1) * loop_dist) + m_map[base_header]
                if calc_miles >= max_miles:
                    max_miles, furthest_station, last_time_str = calc_miles, base_header, val_str

    if "dnf" in " ".join(row.astype(str)).lower(): 
        return "DNF", max_miles, "---", 999999, "---"
    if max_miles >= total_race_dist: 
        return "Finished!", total_race_dist, "---", 0, "N/A"
    if max_miles == 0: 
        return "Not Started", 0.0, "---", 999999, "<b>Middle out</b>"

    return f"<b>{furthest_station}</b>", max_miles, "In Progress", 500, "---"

@st.cache_data(ttl=30)
def load_data(mode, query=""):
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    try:
        # Load the raw CSV
        df = pd.read_csv(url)
        df.columns = [str(c).strip() for c in df.columns]
        
        # POSITIONAL SELECTION: 
        # Column 0 is always the Team/Runner name
        # Column 1 is always the Bib
        name_col_name = df.columns[0]
        bib_col_name = df.columns[1]

        # Clean Bibs to ensure they are numbers
        df[bib_col_name] = pd.to_numeric(df[bib_col_name], errors='coerce')
        
        # Filter: Only rows that have a valid Bib number
        df = df[df[bib_col_name].notna()]

        # Filter: Relay is 400-499
        is_relay = (df[bib_col_name] >= 400) & (df[bib_col_name] < 500)
        active_df = df[is_relay].copy() if mode == "Relay" else df[~is_relay].copy()

        # Final check: Remove any row where the name is literally "Runner", "Team", or "Status"
        active_df = active_df[~active_df[name_col_name].astype(str).str.lower().isin(['runner', 'team', 'status'])]

        if query:
            active_df = active_df[active_df[name_col_name].astype(str).str.contains(query, case=False) | 
                                  active_df[bib_col_name].astype(str).str.contains(query)]

        # Check for any timestamps (":") to see if race data is live
        global_has_data = active_df.astype(str).apply(lambda x: x.str.contains(":")).any().any()

        results = []
        for _, row in active_df.iterrows():
            status, miles, r_time, s_sec, expected = get_status(row, mode, global_has_data)
            results.append({
                "Pos": 0, 
                "Team/Runner": row[name_col_name], 
                "Bib": int(row[bib_col_name]),
                "Status": status, 
                "Total Miles": miles, 
                "Race Time": r_time, 
                "Expected": expected, 
                "SortSec": s_sec
            })

        if not results: return pd.DataFrame()

        full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'SortSec'], ascending=[False, True])
        
        # Positioning for runners with mileage
        mask = (full_df['Total Miles'] > 0) & (~full_df['Status'].str.contains("Not Started|Race"))
        full_df.loc[mask, 'Pos'] = range(1, mask.sum() + 1)
        full_df.loc[~mask, 'Pos'] = ""
        
        return full_df.drop(columns=['SortSec'])
    except Exception as e:
        st.error(f"Syncing data... ({e})")
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
        th { background-color: #f2f2f2; padding: 12px; border: 1px solid #ddd; font-weight: bold; }
        td { padding: 12px; border: 1px solid #ddd; text-align: center; vertical-align: middle; }
        td:nth-child(2) { text-align: left; font-weight: 500; }
    </style>""", unsafe_allow_html=True)
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No participants found in this category.")
