import streamlit as st
import pandas as pd
import requests
import io
import datetime

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Live", layout="wide")

# 2. Hardcoded Essentials
STATION_NAMES = ["Middle Out", "Conant Rd", "Middle Back", "Arrive S/F"]
M_100 = [4.5, 13.0, 20.5, 25.0]
M_RELAY = [3.5, 10.5, 16.5, 20.0]

# YOUR EXACT COLUMN INDICES
MAP = {
    1: [6, 7, 8, 11],
    2: [12, 13, 14, 17],
    3: [18, 19, 20, 23],
    4: [24, 25, 26, 29],
    5: [30, 31, 32, 35]
}

def parse_mins(val):
    """Forceful manual parse of 'HH:MM' string."""
    try:
        s = str(val).strip().upper().replace(" AM", "").replace(" PM", "")
        if ":" not in s: return None
        h, m = map(int, s.split(":"))
        if "PM" in str(val).upper() and h < 12: h += 12
        if h < 6: h += 24 # Overnight Sunday
        return (h * 60 + m) - 360 # Minutes since 6:00 AM
    except:
        return None

def process_row(row, mode):
    dist_list = M_100 if mode == "100 Miler" else M_RELAY
    l_size = 25.0 if mode == "100 Miler" else 20.0
    
    # Default state: At the start line
    miles, stat, t_str, t_mins, lp = 0.0, "Start", "6:00 AM", 0, 1
    
    # Scan every mapped column for the furthest valid time
    for lap_num, col_indices in MAP.items():
        for i, col_idx in enumerate(col_indices):
            if col_idx < len(row):
                val = row.iloc[col_idx]
                m = parse_mins(val)
                if m is not None:
                    # Found a further point
                    current_dist = ((lap_num - 1) * l_size) + dist_list[i]
                    if current_dist >= miles:
                        miles, stat, t_str, t_mins, lp = current_dist, STATION_NAMES[i], str(val), m, lap_num
    return miles, stat, t_str, t_mins, lp

# 3. Data Fetch
@st.cache_data(ttl=0)
def fetch():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv"
    r = requests.get(url)
    return pd.read_csv(io.StringIO(r.text), header=None, dtype=str)

raw_df = fetch()
view = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)

results = []
for _, row in raw_df.iterrows():
    name = str(row.iloc[0]).strip()
    bib = str(row.iloc[1]).strip()
    
    if bib.isdigit() and len(name) > 1:
        is_relay = 400 <= int(bib) < 500
        if (view == "Relay") == is_relay:
            m, s, ts, tm, lp = process_row(row, view)
            
            # Calculations
            mph = round(m / (tm / 60), 1) if tm > 0 else 0.0
            r_time = f"{tm // 60}h {tm % 60}m"
            
            # Expected Next
            exp = "---"
            max_d = 100.0 if view == "100 Miler" else 100.0 # Both are 100 total
            if mph > 0 and m < max_d:
                c_idx = STATION_NAMES.index(s)
                n_idx = (c_idx + 1) % 4
                n_st = STATION_NAMES[n_idx]
                target_lp = lp + 1 if (n_idx == 0 and c_idx == 3) else lp
                n_dist = ((target_lp - 1) * (25.0 if view == "100 Miler" else 20.0)) + (M_100[n_idx] if view == "100 Miler" else M_RELAY[n_idx])
                
                eta_m = tm + ((n_dist - m) / mph * 60)
                # Convert back to Clock Time
                clock_m = (eta_m + 360) % 1440
                h, mi = int(clock_m // 60), int(clock_m % 60)
                ap = "AM" if h < 12 or h >= 24 else "PM"
                dh = h if h <= 12 else h - 12
                if dh == 0: dh = 12
                exp = f"<b>{n_st}</b><br>{dh}:{mi:02d} {ap}"

            results.append({
                "Pos": 0, "Name": name, "Bib": bib, "Miles": m,
                "Status (Last Seen)": f"<b>{s}</b><br>{ts}",
                "Expected Next": exp, "MPH": mph, "Race Time": r_time, 
                "Loop": lp, "sort": (m * 10000) - tm
            })

if results:
    f_df = pd.DataFrame(results).sort_values("sort", ascending=False)
    f_df["Pos"] = range(1, len(f_df) + 1)
    st.write(f_df[["Pos", "Name", "Bib", "Miles", "Status (Last Seen)", "Expected Next", "MPH", "Race Time", "Loop"]].to_html(escape=False, index=False), unsafe_allow_html=True)
