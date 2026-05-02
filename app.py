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
        st.write("*(Logo Placeholder: logo.jpg)*")

st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)

# 2. Time Logic
utc_now = datetime.datetime.utcnow()
now = utc_now - datetime.timedelta(hours=4) 
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

if now < START_TIME:
    st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
    st.write("**Hours until Race Day!**")
else:
    st.write("**Race in Progress**")

# 3. Data Processing Logic
STATION_MILES_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
STATION_MILES_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

def get_status(row, mode, has_data):
    m_map = STATION_MILES_100 if mode == "100 Miler" else STATION_MILES_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    
    if not has_data:
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

    if max_miles == 0: return "Ready", 0.0, 999999, "<b>Middle out</b>"
    return f"<b>{furthest_station}</b>", max_miles, 500, "---"

@st.cache_data(ttl=30)
def load_data(mode, query=""):
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    try:
        # Load everything as strings to avoid auto-conversion errors
        df = pd.read_csv(url, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        
        # Find Bib index
        bib_idx = next((i for i, c in enumerate(df.columns) if "Bib" in c), None)
        if bib_idx is None: return pd.DataFrame()

        # Based on image_125eb4.png: 
        # [Runner Name] [Ranking] [Bib]
        name_col = df.columns[bib_idx - 2] 
        bib_col = df.columns[bib_idx]
            
        # Convert Bib to numeric for filtering
        df['_bib_num'] = pd.to_numeric(df[bib_col], errors='coerce')
        df = df.dropna(subset=['_bib_num'])
        
        is_relay = (df['_bib_num'] >= 400) & (df['_bib_num'] < 500)
        active_df = df[is_relay].copy() if mode == "Relay" else df[~is_relay].copy()
            
        if query:
            active_df = active_df[active_df[name_col].str.contains(query, case=False, na=False)]
        
        # Check if any timestamps exist
        has_data = active_df.astype(str).apply(lambda x: x.str.contains(":")).any().any()
        
        results = []
        for _, row in active_df.iterrows():
            status, miles, s_sec, expected = get_status(row, mode, has_data)
            results.append({
                "Pos": None, 
                "Team/Runner": row[name_col], 
                "Bib": str(int(row['_bib_num'])),
                "Status": status, 
                "Total Miles": miles, 
                "Expected": expected, 
                "Sort": s_sec
            })
        
        if not results: return pd.DataFrame()
        
        full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'Sort'], ascending=[False, True])
        
        # Calculate Rank only for those who have started
        mask = (full_df['Total Miles'] > 0)
        if mask.any():
            full_df.loc[mask, 'Pos'] = range(1, mask.sum() + 1)
        
        # Replace NaN with empty string to avoid the 'int64' error during display
        full_df['Pos'] = full_df['Pos'].fillna("")
        
        return full_df.drop(columns=['Sort'])
        
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# 4. UI Rendering
view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search = st.text_input("🔍 Search Name:") if view_mode == "100 Miler" else ""

if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

data = load_data(view_mode, search)

if not data.empty:
    # Use HTML to ensure "Pos" stays empty where intended
    st.markdown("""<style>
        table { width: 100%; border-collapse: collapse; }
        th { background-color: #f2f2f2; padding: 10px; border: 1px solid #ddd; text-align: center !important; }
        td { padding: 10px; border: 1px solid #ddd; text-align: center !important; }
        td:nth-child(2) { text-align: left !important; font-weight: bold; }
    </style>""", unsafe_allow_html=True)
    
    st.write(data.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No data found.")
