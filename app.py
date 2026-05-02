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

# 3. Timezone Logic
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) 
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
DNS_CUTOFF = datetime.datetime(2026, 5, 2, 7, 30, 0)
RACE_LIMIT_HOURS = 32

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

if now < START_TIME:
    st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
    st.write("**Hours until Race Day!**")
else:
    elapsed_diff = now - START_TIME
    display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
    st.subheader(f"⏱️ {format_delta_hhh(display_elapsed)}")
    st.write("**Elapsed Race Time**")

# 4. Data Processing Logic
STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

def get_status(row, mode, global_has_data):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    
    if not global_has_data:
        return "Race starts May 2nd @ 6am", 0.0, 999999, "---"

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
    if "dnf" in row_str: return "DNF", max_miles, 999999, "---"
    if max_miles >= 100.0: return "Finished!", 100.0, 0, "N/A"
    if max_miles == 0: return "Not Started", 0.0, 999999, "<b>Middle out</b>"
    return f"<b>{furthest_station}</b>", max_miles, 500, "---"

@st.cache_data(ttl=30)
def load_data(mode, query=""):
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    try:
        df = pd.read_csv(url, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        
        # FIND THE BIB COLUMN
        bib_idx = next((i for i, c in enumerate(df.columns) if "Bib" in c), None)
        if bib_idx is None: return pd.DataFrame()

        # RE-TARGET: Name is 2 columns back from Bib
        # Ranking is 1 column back (which we skip)
        name_col = df.columns[bib_idx - 2]
        bib_col = df.columns[bib_idx]
            
        df['_n'] = pd.to_numeric(df[bib_col], errors='coerce')
        df = df.dropna(subset=['_n'])
        
        is_relay = (df['_n'] >= 400) & (df['_n'] < 500)
        active_df = df[is_relay].copy() if mode == "Relay" else df[~is_relay].copy()
            
        active_df = active_df[active_df[name_col].notna()]

        if query:
            active_df = active_df[active_df[name_col].str.contains(query, case=False, na=False)]
        
        has_data = active_df.astype(str).apply(lambda x: x.str.contains(":")).any().any()
        
        results = []
        for _, row in active_df.iterrows():
            status, miles, s_sec, expected = get_status(row, mode, has_data)
            results.append({
                "Pos": 0, "Team/Runner": row[name_col], "Bib": str(int(row['_n'])),
                "Status": status, "Total Miles": miles, "Expected": expected, "Sort": s_sec
            })
        
        if not results: return pd.DataFrame()
        
        full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'Sort'], ascending=[False, True])
        mask = (full_df['Total Miles'] > 0) & (~full_df['Status'].str.contains("DNF|DNS|Race"))
        full_df.loc[mask, 'Pos'] = range(1, mask.sum() + 1)
        full_df.loc[~mask, 'Pos'] = ""
        return full_df.drop(columns=['Sort'])
        
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# 5. UI
view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search = st.text_input("🔍 Search Name:") if view_mode == "100 Miler" else ""

if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

data = load_data(view_mode, search)
if not data.empty:
    st.markdown("""<style>
        table { width: 100%; border-collapse: collapse; }
        th { background-color: #f2f2f2; padding: 12px; border: 1px solid #ddd; }
        td { padding: 12px; border: 1px solid #ddd; text-align: center; }
        td:nth-child(2) { text-align: left; font-weight: bold; }
    </style>""", unsafe_allow_html=True)
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No data found.")
