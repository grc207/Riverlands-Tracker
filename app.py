import streamlit as st
import pandas as pd
import datetime
import time
from difflib import SequenceMatcher

# 1. Setup & Constants
st.set_page_config(page_title="Riverlands 100 Tracker", layout="wide")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0"
START_TIME = datetime.datetime(2026, 5, 2, 6, 0)
RACE_LIMIT_HOURS = 32

# Mileage Constants
MAP_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Start/Finish": 25.0}
MAP_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Start/Finish": 20.0}

# --- HELPER FUNCTIONS ---

def format_delta_hhh(delta):
    """Formats a timedelta into HHH:MM:SS."""
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

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

def get_status(row, mode, now):
    station_data = row.iloc[2:] 
    last_val, last_loc, total_miles, current_loop, has_data = "", "Start", 0.0, 1, False
    
    mileage_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    station_counts = {"Middle out": 0, "Conant Rd": 0, "Middle back": 0, "Start/Finish": 0}
    
    # Fail-safe logic
    gap_counter = 0 
    is_manual_dnf = row.astype(str).str.contains('DNF|dnf').any()

    for col_name, val in station_data.items():
        val_str = str(val).strip() if pd.notnull(val) else ""
        clean_name = str(col_name).split('.')[0].strip()

        if clean_name in station_counts:
            if val_str != "" and "dnf" not in val_str.lower():
                gap_counter = 0 # Reset gap
                station_counts[clean_name] += 1
                loop_idx = station_counts[clean_name] - 1
                has_data, last_val, last_loc = True, val_str, clean_name
                current_loop = station_counts[clean_name]
                total_miles = (loop_idx * loop_dist) + mileage_map[clean_name]
            else:
                gap_counter += 1
                if gap_counter >= 2: # FAIL-SAFE TRIGGERED
                    break
        else:
            continue

    # 1. Determine Status Text
    if total_miles >= 100.0:
        status_text, sort_weight = "Finished!", 100.0
    elif has_data:
        status_text, sort_weight = last_loc, total_miles
    else:
        # NEW: Time-based logic for runners with no check-ins
        if now < START_TIME:
            status_text = "Starts May 2nd @ 6am"
        elif now < (START_TIME + datetime.timedelta(hours=1.5)):
            status_text = "Race Started"
        else:
            status_text = "DNS"
        sort_weight = -2.0

    if is_manual_dnf:
        status_text, sort_weight = "DNF", -1.0
    
    elapsed_str, elapsed_seconds = calculate_elapsed(last_val, current_loop, status_text)
    return status_text, total_miles, sort_weight, last_val, current_loop, elapsed_str, elapsed_seconds

@st.cache_data(ttl=30)
def load_data(mode, now):
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    df['Bib'] = pd.to_numeric(df['Bib'], errors='coerce')
    
    if mode == "100 Miler":
        sub_df = df[df['Bib'] >= 300].copy()
    else:
        sub_df = df[df['Bib'] < 300].copy()
        sub_df = sub_df[sub_df['Team/Runner'].notna()]
    
    results = []
    for _, row in sub_df.iterrows():
        status, miles, s_weight, l_time, loop, el_str, el_sec = get_status(row, mode, now)
        results.append({
            "Team/Runner": row['Team/Runner'],
            "Bib": int(row['Bib']) if pd.notnull(row['Bib']) else 0,
            "Status": status,
            "Miles": miles,
            "SortWeight": s_weight,
            "Time": l_time,
            "Elapsed": el_str,
            "SortSeconds": el_sec if el_sec is not None else 999999,
            "Lap": loop
        })
    
    full_df = pd.DataFrame(results).sort_values(by=['SortWeight', 'SortSeconds'], ascending=[False, True])
    full_df.insert(0, 'Pos', range(1, len(full_df) + 1))
    full_df.loc[full_df['SortWeight'] < 0, 'Pos'] = None
    return full_df

# --- UI ---

# Header & Timer Logic
now = datetime.datetime.now()

# 1. Display the Logo (centered)
st.image("logo.jpg", use_container_width=True)

# 2. Display the Title (removing the runner emoji)
st.title("Riverlands 100 Live Leaderboard")

# Dynamic Clock Container
with st.container():
    if now < START_TIME:
        time_diff = START_TIME - now
        st.subheader(f"⏱️ {format_delta_hhh(time_diff)}")
        st.write("**Hours Until Race Day!**")
    else:
        elapsed_diff = now - START_TIME
        # Cap at 32 hours
        if elapsed_diff > datetime.timedelta(hours=RACE_LIMIT_HOURS):
            elapsed_diff = datetime.timedelta(hours=RACE_LIMIT_HOURS)
        
        st.subheader(f"⏱️ {format_delta_hhh(elapsed_diff)}")
        st.write("**Elapsed Race Time**")

st.info("**Disclaimer:** This is an independent project and is not maintained by the race director. "
        "All information may not be timely or accurate.\n\n"
        "Some updates may take a few minutes to refresh.")

view_mode = st.radio("Select Category:", ["100 Miler", "Relay"], horizontal=True)

if view_mode == "100 Miler":
    query = st.text_input("Search Name or Bib", placeholder="Search runners...")
else:
    query = ""

try:
    master_df = load_data(view_mode, now)
    
    if query and view_mode == "100 Miler":
        mask = master_df.apply(lambda r: fuzzy_match(query, r['Team/Runner']) or query in str(r['Bib']), axis=1)
        display_df = master_df[mask]
    else:
        display_df = master_df

    st.dataframe(
        display_df.drop(columns=['SortWeight', 'SortSeconds']),
        column_config={
            "Miles": st.column_config.NumberColumn("Total Miles", format="%.1f"),
            "Pos": st.column_config.NumberColumn("Pos", format="%d"),
            "Elapsed": "Race Time",
            "Time": "Time of Day"
        },
        use_container_width=True, hide_index=True
    )
except Exception as e:
    st.error("Updating leaderboard...")
