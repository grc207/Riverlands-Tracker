import streamlit as st
import pandas as pd
import datetime
import requests
import io

# 1. Setup & Branding
st.set_page_config(page_title="Riverlands 100 Live Tracker", layout="wide")

# Logo and Header
col1, col2 = st.columns([1, 5])
with col1:
    # Using the official Riverlands logo URL
    st.image("https://riverlands100.com/wp-content/uploads/2021/01/Riverlands-Logo-1.png", width=120)
with col2:
    st.title("Riverlands 100 Live Tracker")
    st.subheader("Real-time Unofficial Leaderboard")

# 2. Hardcoded Essentials
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
        if not any(c.isdigit() for c in val): return None
        if ":" not in val: return None
        
        ts = pd.to_datetime(val).time()
        dt = datetime.datetime(2026, 5, 2, ts.hour, ts.minute)
        
        if ts.hour < 6: 
            dt += datetime.timedelta(days=1)
            
        return int((dt - START_TIME).total_seconds() // 60)
    except:
        return None

def get_runner_data(row, mode):
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
        if not lap_found:
            break
            
    return best_dist, best_stat, best_time_str, best_time_mins, best_loop

# 3. Load & Process
@st.cache_data(ttl=0)
def load():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    res = requests.get(url)
    return pd.read_csv(io.StringIO(res.text), header=None, dtype=str)

df = load()
view = st.sidebar.radio("View Race:", ["100 Miler", "Relay"])
if st.sidebar.button("Manual Refresh"):
    st.cache_data.clear()
    st.rerun()

results = []
for i in range(len(df)):
    row = df.iloc[i]
    name, bib = str(row.iloc[0]).strip(), str(row.iloc[1]).strip()
    
    if bib.isdigit() and len(name) > 1:
        b_val = int(bib)
        is_relay = 400 <= b_val < 500
        if (view == "Relay") == is_relay:
            miles, stat, t_str, t_mins, loop = get_runner_data(row, view)
            
            mph = round(miles / (t_mins / 60), 1) if t_mins > 0 else 0.0
            r_time = f"{t_mins // 60}h {t_mins % 60}m" if t_mins > 0 else "0h 0m"
            
            exp_html = "---"
            if mph > 0 and miles < 100.0:
                curr_idx = STATION_NAMES.index(stat)
                next_idx = (curr_idx + 1) % 4
                target_lp = loop + 1 if (next_idx == 0 and curr_idx == 3) else loop
                dist_list = M_100 if view == "100 Miler" else M_RELAY
                l_sz = 25.0 if view == "100 Miler" else 20.0
                next_d = ((target_lp - 1) * l_sz) + dist_list[next_idx]
                
                eta_total_mins = t_mins + ((next_d - miles) / mph * 60)
                eta_dt = START_TIME + datetime.timedelta(minutes=eta_total_mins)
                exp_html = f"<b>{STATION_NAMES[next_idx]}</b><br>{eta_dt.strftime('%-I:%M %p')}"

            results.append({
                "Pos": 0, "Name": name, "Bib": bib, "Miles": miles,
                "Status": f"<b>{stat}</b><br>{t_str}",
                "Expected": exp_html, "MPH": mph, "Race Time": r_time, 
                "Loop": loop, "sort": (miles * 10000) - t_mins
            })

# 4. Display Table
if results:
    f_df = pd.DataFrame(results).sort_values("sort", ascending=False)
    f_df["Pos"] = range(1, len(f_df) + 1)
    display_cols = ["Pos", "Name", "Bib", "Miles", "Status", "Expected", "MPH", "Race Time", "Loop"]
    st.write(f_df[display_cols].to_html(escape=False, index=False), unsafe_allow_html=True)

# 5. Disclaimer
st.markdown("---")
st.caption("""
**Disclaimer:** This tracker is a community-led project and is NOT the official timing system. 
Data is synced from manual entries at aid stations; delays or errors may occur due to connectivity. 
Always refer to official race officials for final standings.
""")
