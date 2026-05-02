import streamlit as st
import pandas as pd
import datetime
import requests
import io

# 1. Setup & Branding
st.set_page_config(page_title="Riverlands 100 Live", layout="wide")

col1, col2 = st.columns([1, 5])
with col1:
    st.image("logo.jpg", width=120)
with col2:
    st.title("Riverlands 100 Live Tracker")
    st.subheader("Real-time Unofficial Leaderboard")

# 2. Constants
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
STATION_NAMES = ["Middle Out", "Conant Rd", "Middle Back", "Arrive S/F"]
M_100 = [4.5, 13.0, 20.5, 25.0]
M_RELAY = [3.5, 10.5, 16.5, 20.0]

MAP = {
    1: [6, 7, 8, 11],
    2: [12, 13, 14, 17],
    3: [18, 19, 20, 23],
    4: [24, 25, 26, 29],
    5: [30, 31, 32, 35] 
}

def clean_time_to_minutes(val):
    try:
        val = str(val).strip().upper()
        if ":" not in val: return None
        ts = pd.to_datetime(val).time()
        dt = datetime.datetime(2026, 5, 2, ts.hour, ts.minute)
        if ts.hour < 6: dt += datetime.timedelta(days=1)
        return int((dt - START_TIME).total_seconds() // 60)
    except:
        return None

def get_runner_data(row, mode):
    is_dnf = row.astype(str).str.contains("DNF", case=False).any()
    dist_list = M_100 if mode == "100 Miler" else M_RELAY
    loop_size = 25.0 if mode == "100 Miler" else 20.0
    max_loops = 4 if mode == "100 Miler" else 5
    
    best_dist, best_time_str, best_time_mins, best_stat, best_loop = 0.0, "---", 0, "Start", 1
    
    for lap in range(1, max_loops + 1):
        lap_cols = MAP[lap]
        lap_found = False
        for i, col_idx in enumerate(lap_cols):
            if col_idx < len(row):
                val = row.iloc[col_idx]
                mins = clean_time_to_minutes(val)
                if mins is not None:
                    best_dist = ((lap - 1) * loop_size) + dist_list[i]
                    best_time_str = str(val).strip()
                    best_time_mins = mins
                    best_stat = STATION_NAMES[i]
                    best_loop = lap
                    lap_found = True
        if not lap_found: break 

    if is_dnf:
        best_stat = "DNF"
        
    return best_dist, best_stat, best_time_str, best_time_mins, best_loop, is_dnf

# 3. Sidebar / Controls
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

view = st.radio("Race Category:", ["100 Miler", "Relay"], horizontal=True)
search_query = st.text_input("Search Runner or Bib:", "").strip().lower()

# 4. Load & Process
@st.cache_data(ttl=0)
def load():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    res = requests.get(url)
    return pd.read_csv(io.StringIO(res.text), header=None, dtype=str)

df = load()
results = []

for i in range(len(df)):
    row = df.iloc[i]
    name, bib = str(row.iloc[0]).strip(), str(row.iloc[1]).strip()
    
    if bib.isdigit() and len(name) > 1:
        is_relay_bib = 400 <= int(bib) < 500
        
        # Category Filter
        if (view == "Relay" and is_relay_bib) or (view == "100 Miler" and not is_relay_bib):
            # Search Filter
            if not search_query or (search_query in name.lower() or search_query in bib):
                miles, stat, t_str, t_mins, loop, is_dnf = get_runner_data(row, view)
                
                mph = round(miles / (t_mins / 60), 1) if t_mins > 0 else 0.0
                r_time = f"{t_mins // 60}h {t_mins % 60}m"
                
                sort_key = (miles * 10000) - t_mins
                if is_dnf: sort_key -= 1000000 
                
                results.append({
                    "Pos": 0, "Name": name, "Bib": bib, "Miles": miles,
                    "Status": f"<b style='color:{'red' if is_dnf else 'black'}'>{stat}</b><br>{t_str}",
                    "MPH": mph, "Race Time": r_time, "Loop": loop, 
                    "sort": sort_key
                })

# 5. Display
if results:
    f_df = pd.DataFrame(results).sort_values("sort", ascending=False)
    f_df["Pos"] = range(1, len(f_df) + 1)
    st.write(f"**Tracking {len(f_df)} Runners**")
    st.write(f_df[["Pos", "Name", "Bib", "Miles", "Status", "MPH", "Race Time", "Loop"]].to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No runners found matching your selection or search.")

st.markdown("---")
st.caption("Disclaimer: This tracker is unofficial and community-led.")
