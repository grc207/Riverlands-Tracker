import streamlit as st
import pandas as pd
import datetime
import time
from difflib import SequenceMatcher

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Tracker", layout="wide")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0"
START_TIME = datetime.datetime(2026, 5, 2, 6, 0)

# Mileage Constants
MAP_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Start/Finish": 25.0}
MAP_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Start/Finish": 20.0}

# --- HELPER FUNCTIONS ---

def fuzzy_match(query, target):
    query, target = str(query).lower(), str(target).lower()
    if query in target: return True 
    return SequenceMatcher(None, query, target).ratio() > 0.7 

def calculate_elapsed(station_time_str, current_loop, last_loc):
    if not station_time_str or str(station_time_str).strip() == "":
        return None, None
    try:
        t = pd.to_datetime(str(station_time_str).strip()).time()
        day = 2
        # If far into the race and time is early morning, it's Sunday (Day 2)
        if current_loop >= 3 and t.hour < 14: day = 3
        if last_loc == "Finished!" and t.hour < 14: day = 3
        
        actual_dt = datetime.datetime(2026, 5, day, t.hour, t.minute)
        delta = actual_dt - START_TIME
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours}h {minutes:02d}m", total_seconds
    except:
        return None, None

def get_status(row, mode):
    """Calculates mileage based on mode (100 Miler vs Relay)."""
    times = row.iloc[2:] 
    last_val, last_loc, total_miles, current_loop, has_data = "", "Start", 0.0, 1, False
    
    # Select correct math
    mileage_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    finish_dist = 100.0 if mode == "100 Miler" else 100.0 # Both are 100 total
    
    is_manual_dnf = row.astype(str).str.contains('DNF|dnf').any()

    for i, (col_name, val) in enumerate(times.items()):
        val_str = str(val).strip() if pd.notnull(val) else ""
        if val_str != "" and "dnf" not in val_str.lower():
            has_data, last_val = True, val_str
            last_loc = str(col_name).split('.')[0].strip()
            loop_idx = i // 4
            current_loop = loop_idx + 1
            if last_loc in mileage_map:
                total_miles = (loop_idx * loop_dist) + mileage_map[last_loc]

    status_text = last_loc
    sort_weight = total_miles
    
    if total_miles >= finish_dist:
        status_text = "Finished!"
        sort_weight = 100.0
    
    if not has_data:
        status_text, sort_weight = "DNS", -2.0
    
    elapsed_str, elapsed_seconds = calculate_elapsed(last_val, current_loop, status_text)
    
    if is_manual_dnf:
        status_text, sort_weight = "DNF", -1.0

    return status_text, total_miles, sort_weight, last_val, current_loop, elapsed_str, elapsed_seconds

@st.cache_data(ttl=30)
def load_data(mode):
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    df['Bib'] = pd.to_numeric(df['Bib'], errors='coerce')
    
    # Split the sheet by Bib range
    if mode == "100 Miler":
        sub_df = df[df['Bib'] >= 300].copy()
    else:
        # Relay teams are the lower bibs (usually 1-200) or anything not 300+
        sub_df = df[df['Bib'] < 300].copy()
        sub_df = sub_df[sub_df['Team/Runner'].notna()] # Ignore empty spacer rows
    
    results = []
    for _, row in sub_df.iterrows():
        status, miles, s_weight, l_time, loop, el_str, el_sec = get_status(row, mode)
        results.append({
            "Team/Runner": row['Team/Runner'],
            "Bib": int(row['Bib']) if pd.notnull(row['Bib']) else 0,
            "Status": status,
            "Miles": miles,
            "SortWeight": s_weight,
            "Time of Day": l_time,
            "Elapsed": el_str,
            "SortSeconds": el_sec if el_sec is not None else 999999,
            "Lap": loop
        })
    
    full_df = pd.DataFrame(results).sort_values(by=['SortWeight', 'SortSeconds'], ascending=[False, True])
    full_df.insert(0, 'Pos', range(1, len(full_df) + 1))
    full_df.loc[full_df['SortWeight'] < 0, 'Pos'] = None
    return full_df

# --- UI BUILD ---

st.title("🏃 Riverlands 100 Live Leaderboard")

# Disclaimer Box
st.warning("**Disclaimer:** This is an independent project and is not maintained by the race director. "
           "All information may not be timely or accurate, and should not be used as the official race tracker.")

# Navigation Radio
view_mode = st.radio("Select Category:", ["100 Miler", "Relay"], horizontal=True)

if view_mode == "100 Miler":
    query = st.text_input("Search Name or Bib", placeholder="Search runners...")
else:
    query = "" # No search for relay per your request

try:
    master_df = load_data(view_mode)
    
    if query and view_mode == "100 Miler":
        mask = master_df.apply(lambda r: fuzzy_match(query, r['Team/Runner']) or query in str(r['Bib']), axis=1)
        display_df = master_df[mask]
    else:
        display_df = master_df

    st.dataframe(
        display_df.drop(columns=['SortWeight', 'SortSeconds']),
        column_config={
            "Miles": st.column_config.NumberColumn("Miles", format="%.1f"),
        },
        use_container_width=True, hide_index=True
    )
except Exception as e:
    st.error("Updating leaderboard...")
