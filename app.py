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

# Mileage Constants & Order for prediction
STATION_ORDER = ["Start", "Middle out", "Conant Rd", "Middle back", "Start/Finish"]
MAP_100 = {"Start": 0.0, "Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Start/Finish": 25.0}
MAP_RELAY = {"Start": 0.0, "Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Start/Finish": 20.0}

# --- HELPER FUNCTIONS ---

def format_delta_hhh(delta):
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
        return None, None, None
    try:
        t = pd.to_datetime(str(station_time_str).strip()).time()
        day = 2
        if current_loop >= 3 and t.hour < 14: day = 3
        if last_loc == "Finished!" and t.hour < 14: day = 3
        actual_dt = datetime.datetime(2026, 5, day, t.hour, t.minute)
        delta = actual_dt - START_TIME
        return f"{hours}h {minutes:02d}m", int(delta.total_seconds()), actual_dt
    except:
        return None, None, None

def get_status(row, mode, now):
    station_data = row.iloc[2:] 
    last_val, last_loc, total_miles, current_loop, has_data = "", "Start", 0.0, 1, False
    last_dt = START_TIME
    
    mileage_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    station_counts = {"Middle out": 0, "Conant Rd": 0, "Middle back": 0, "Start/Finish": 0}
    
    is_manual_dnf = row.astype(str).str.contains('DNF|dnf').any()

    for col_name, val in station_data.items():
        val_str = str(val).strip() if pd.notnull(val) else ""
        clean_name = str(col_name).split('.')[0].strip()

        if clean_name in station_counts:
            if val_str != "" and "dnf" not in val_str.lower():
                station_counts[clean_name] += 1
                loop_idx = station_counts[clean_name] - 1
                has_data, last_val, last_loc = True, val_str, clean_name
                current_loop = station_counts[clean_name]
                total_miles = (loop_idx * loop_dist) + mileage_map[clean_name]
                
                # Get actual timestamp for ETA math
                try:
                    t = pd.to_datetime(val_str).time()
                    day = 2 if not (current_loop >= 3 and t.hour < 14) else 3
                    last_dt = datetime.datetime(2026, 5, day, t.hour, t.minute)
                except: pass

    if total_miles >= 100.0:
        status_text, sort_weight = "Finished!", 100.0
    elif has_data:
        status_text, sort_weight = last_loc, total_miles
    else:
        status_text = "Race Started" if now >= START_TIME else "Starts May 2nd"
        sort_weight = -2.0

    if is_manual_dnf:
        status_text, sort_weight = "DNF", -1.0
    
    elapsed_str, elapsed_seconds, last_actual_dt = calculate_elapsed(last_val, current_loop, status_text)
    return status_text, total_miles, sort_weight, last_val, current_loop, elapsed_str, elapsed_seconds, last_actual_dt

@st.cache_data(ttl=30)
def load_data(mode, now):
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    df['Bib'] = pd.to_numeric(df['Bib'], errors='coerce')
    
    sub_df = df[df['Bib'] >= 300].copy() if mode == "100 Miler" else df[df['Bib'] < 300].copy()
    if mode != "100 Miler": sub_df = sub_df[sub_df['Team/Runner'].notna()]
    
    mileage_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    results = []
    
    for _, row in sub_df.iterrows():
        status, miles, s_weight, l_time, loop, el_str, el_sec, l_dt = get_status(row, mode, now)
        
        avg_pace = miles / (el_sec / 3600) if el_sec and el_sec > 0 else 0.0
        
        # --- ETA LOGIC ---
        eta_display = "---"
        if status not in ["Finished!", "DNF", "DNS"] and avg_pace > 0:
            try:
                curr_idx = STATION_ORDER.index(status)
                next_station = STATION_ORDER[0] if status == "Start/Finish" else STATION_ORDER[curr_idx + 1]
                
                # Distance to next point
                dist_to_next = mileage_map[next_station] - mileage_map[status]
                if dist_to_next <= 0: dist_to_next = mileage_map["Middle out"] # Lap rollover
                
                hours_to_next = dist_to_next / avg_pace
                arrival_dt = (l_dt or START_TIME) + datetime.timedelta(hours=hours_to_next)
                eta_display = f"{next_station} @ {arrival_dt.strftime('%I:%M %p').lstrip('0')}"
            except: pass

        results.append({
            "Team/Runner": row['Team/Runner'],
            "Bib": int(row['Bib']) if pd.notnull(row['Bib']) else 0,
            "Status": status,
            "Miles": miles,
            "SortWeight": s_weight,
            "Time": l_time,
            "Elapsed": el_str,
            "Average Pace": avg_pace,
            "Expected Arrival": eta_display,
            "SortSeconds": el_sec if el_sec is not None else 999999
        })
    
    full_df = pd.DataFrame(results).sort_values(by=['SortWeight', 'SortSeconds'], ascending=[False, True])
    full_df.insert(0, 'Pos', range(1, len(full_df) + 1))
    full_df.loc[full_df['SortWeight'] < 0, 'Pos'] = None
    return full_df

# --- UI ---
now = datetime.datetime.now()
st.image("logo.jpg", width=250)
st.title("Riverlands 100 Live Leaderboard")

with st.container():
    elapsed_diff = now - START_TIME
    if now < START_TIME:
        st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
        st.write("**Hours Until Race Day!**")
    else:
        st.subheader(f"⏱️ {format_delta_hhh(min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS)))}")
        st.write("**Elapsed Race Time**")

st.info("**Disclaimer:** Independent project. Not official timing data.")

view_mode = st.radio("Select Category:", ["100 Miler", "Relay"], horizontal=True)
query = st.text_input("Search Name or Bib", placeholder="Search...") if view_mode == "100 Miler" else ""

try:
    master_df = load_data(view_mode, now)
    display_df = master_df if not query else master_df[master_df.apply(lambda r: fuzzy_match(query, r['Team/Runner']) or query in str(r['Bib']), axis=1)]

    st.dataframe(
        display_df.drop(columns=['SortWeight', 'SortSeconds']),
        column_config={
            "Miles": st.column_config.NumberColumn("Total Miles", format="%.1f"),
            "Average Pace": st.column_config.NumberColumn("Avg Speed", format="%.2f mph"),
            "Expected Arrival": "Next Expected Location",
            "Elapsed": "Race Time",
            "Time": "Last Seen"
        },
        use_container_width=True, hide_index=True
    )
except Exception as e:
    st.error("Updating leaderboard...")
