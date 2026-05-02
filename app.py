import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Live Leaderboard", layout="wide")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo.jpg", use_container_width=True)
    except:
        st.write("*(Logo: logo.jpg)*")

st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)

# 2. Race Time Logic
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) 
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)

if now < START_TIME:
    delta = START_TIME - now
    st.subheader(f"⏱️ {delta.days * 24 + delta.seconds // 3600}h {(delta.seconds // 60) % 60:02d}m")
    st.write("**Countdown to Race Start**")
else:
    st.write("**Race in Progress**")

# 3. Data Processing
STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

def get_status(row, mode, has_data):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    
    # REMOVED DNS CHECK: If no race data exists, just show the start time info
    if not has_data: 
        return "Race starts May 2nd @ 6am", 0.0, 999999, "<b>Middle out</b>"

    max_miles, furthest_station = 0.0, ""
    for col_name, val in row.items():
        val_str = str(val).strip().lower()
        if ":" in val_str:
            base = col_name.split('.')[0].strip()
            if "Start/Finish" in base: base = "Arrive S/F"
            if base in m_map:
                try: lap = int(col_name.split('.')[-1]) + 1 if "." in col_name else 1
                except: lap = 1
                dist = ((lap - 1) * loop_dist) + m_map[base]
                if dist >= max_miles: max_miles, furthest_station = dist, base

    # If the race has data but this specific runner hasn't hit a station yet
    if max_miles == 0: 
        return "Waiting to Start", 0.0, 999999, "<b>Middle out</b>"
        
    return f"<b>{furthest_station}</b>", max_miles, 500, "---"

@st.cache_data(ttl=30)
def load_data(mode, query=""):
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    try:
        df = pd.read_csv(url, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        
        # TARGETED COLUMN PICKING based on image_11f919.png
        name_col = next((c for c in df.columns if "Team/Runner" in c), None)
        bib_col = next((c for c in df.columns if "Bib" in c), None)

        if not name_col or not bib_col:
            st.error("Could not find 'Team/Runner' or 'Bib' columns.")
            return pd.DataFrame()

        # Filter valid bibs
        df['_bib_num'] = pd.to_numeric(df[bib_col], errors='coerce')
        df = df.dropna(subset=['_bib_num'])
        
        is_relay = (df['_bib_num'] >= 400) & (df['_bib_num'] < 500)
        active_df = df[is_relay].copy() if mode == "Relay" else df[~is_relay].copy()
            
        if query:
            active_df = active_df[active_df[name_col].str.contains(query, case=False, na=False)]
        
        # Check if any station data (timestamps) exists yet
        has_data = active_df.astype(str).apply(lambda x: x.str.contains(":")).any().any()
        
        results = []
        for _, row in active_df.iterrows():
            status, miles, s_sec, expected = get_status(row, mode, has_data)
            results.append({
                "Pos": "", 
                "Team/Runner": row[name_col], 
                "Bib": str(int(row['_bib_num'])),
                "Status": status, 
                "Total Miles": miles, 
                "Expected": expected, 
                "Sort": s_sec
            })
        
        if not results: return pd.DataFrame()
        full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'Sort'], ascending=[False, True])
        
        # Ranking
        mask = (full_df['Total Miles'] > 0)
        if mask.any():
            full_df.loc[mask, 'Pos'] = range(1, mask.sum() + 1)
        
        full_df['Pos'] = full_df['Pos'].astype(str).replace(['nan', 'None'], '')
        return full_df.drop(columns=['Sort'])
        
    except Exception as e:
        st.error(f"Syncing Error: {e}")
        return pd.DataFrame()

# 4. UI
view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search = st.text_input("🔍 Search Name:") if view_mode == "100 Miler" else ""

if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

data = load_data(view_mode, search)

if not data.empty:
    st.markdown("""<style>
        table { width: 100%; border-collapse: collapse; }
        th { background-color: #f2f2f2; padding: 10px; border: 1px solid #ddd; }
        td { padding: 10px; border: 1px solid #ddd; text-align: center !important; }
        td:nth-child(2) { text-align: left !important; font-weight: bold; }
    </style>""", unsafe_allow_html=True)
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No data found.")
