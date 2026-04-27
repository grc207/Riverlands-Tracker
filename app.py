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
GRACE_PERIOD_SECONDS = 60 
MAX_ALLOWED_SECONDS = (RACE_LIMIT_HOURS * 3600) + GRACE_PERIOD_SECONDS
END_TIME = START_TIME + datetime.timedelta(hours=RACE_LIMIT_HOURS)

# Mileage Constants (Updated station name to match new data source)
STATION_ORDER = ["Start", "Middle out", "Conant Rd", "Middle back", "Arrive S/F"]
MAP_100 = {"Start": 0.0, "Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
MAP_RELAY = {"Start": 0.0, "Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

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
        # Handle cases where there might be text alongside the time
        clean_time = str(station_time_str).strip().split(' ')[0]
        t = pd.to_datetime(clean_time).time()
        day = 2
        if current_loop >= 3 and t.hour < 14: day = 3
        if last_loc == "Finished!" and t.hour < 14: day = 3
        
        actual_dt = datetime.datetime(2026, 5, day, t.hour, t.minute)
        delta = actual_dt - START_TIME
        total_sec = int(delta.total_seconds())
        hours, remainder = divmod(total_sec, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours}h {minutes:02d}m", total_sec, actual_dt
    except:
        return None, None, None

def get_status(row, mode, now):
    # Filter the row to only include relevant timing columns
    # We ignore "Leaving S/F" and any "Bib" columns after the first one
    valid_stations = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F", "Start/Finish"]
    
    last_val, last_loc, total_miles, current_loop, has_data = "", "Start", 0.0, 1, False
    mileage_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    
    station_counts = {"Middle out": 0, "Conant Rd": 0, "Middle back": 0, "Arrive S/F": 0}
    is_manual_dnf = row.astype(str).str.contains('DNF|dnf').any()

    for col_name, val in row.items():
        val_str = str(val).strip() if pd.notnull(val) else ""
        if val_str == "" or "dnf" in val_str.lower():
            continue

        # Clean header name (removes .1, .2 added by pandas for duplicate names)
        clean_name = str(col_name).split('.')[0].strip()
        
        # FAILSAFE: Map "Start/Finish" to "Arrive S/F" automatically
        if clean_name == "Start/Finish":
            clean_name = "Arrive S/F"

        if clean_name in station_counts:
            station_counts[clean_name] += 1
            loop_idx = station_counts[clean_name] - 1
            has_data, last_val, last_loc = True, val_str, clean_name
            current_loop = station_counts[clean_name]
            total_miles = (loop_idx * loop_dist) + mileage_map[clean_name]

    # Calculate time based on last check-in
    el_str, el_sec, actual_dt = calculate_elapsed(last_val, current_loop, last_loc)

    # Status Determination
    if total_miles >= 100.0 and (el_sec is not None and el_sec <= MAX_ALLOWED_SECONDS):
        status_text, sort_weight = "Finished!", 100.0
    elif has_data:
        status_text, sort_weight = last_loc, total_miles
    else:
        if now < START_TIME:
            status_text = "Starts May 2nd @ 6am"
        elif now < (START_TIME + datetime.timedelta(hours=1.5)):
            status_text = "Race Started"
        else:
            status_text = "DNS"
        sort_weight = -2.0

    if is_manual_dnf or (now > END_TIME and status_text != "Finished!" and status_text != "DNS"):
        if status_text != "Finished!":
            status_text, sort_weight = "DNF", -1.0
    
    return status_text, total_miles, sort_weight, last_val, current_loop, el_str, el_sec, actual_dt

@st.cache_data(ttl=30)
def load_data(mode, now):
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    
    # Identify the first 'Bib' column specifically
    bib_col = [c for c in df.columns if 'Bib' in c][0]
    df['Bib_Clean'] = pd.to_numeric(df[bib_col], errors='coerce')
    
    sub_df = df[df['Bib_Clean'] >= 300].copy() if mode == "100 Miler" else df[df['Bib_Clean'] < 300].copy()
    if mode != "100 Miler": sub_df = sub_df[sub_df['Team/Runner'].notna()]
    
    mileage_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    results = []
    
    for _, row in sub_df.iterrows():
        status, miles, s_weight, l_time, loop, el_str, el_sec, l_dt = get_status(row, mode, now)
        avg_pace = miles / (el_sec / 3600) if el_sec and el_sec > 0 else 0.0
        
        eta_display = "---"
        if status not in ["Finished!", "DNF", "DNS", "Race Started"] and avg_pace > 0 and now < END_TIME:
            try:
                curr_idx = STATION_ORDER.index(status)
                next_station = STATION_ORDER[0] if status == "Arrive S/F" else STATION_ORDER[curr_idx + 1]
                dist_to_next = mileage_map["Middle out"] if status == "Arrive S/F" else mileage_map[next_station] - mileage_map[status]
                hours_to_next = dist_to_next / avg_pace
                arrival_dt = l_dt + datetime.timedelta(hours=hours_to_next)
                eta_display = f"{next_station} @ {arrival_dt.strftime('%I:%M %p').lstrip('0')}"
            except: eta_display = "TBD"

        results.append({
            "Pos": None if s_weight < 0 else 0,
            "Team/Runner": row['Team/Runner'],
            "Bib": int(row['Bib_Clean']) if pd.notnull(row['Bib_Clean']) else 0,
            "Status": status,
            "Miles": miles,
            "SortWeight": s_weight,
            "Last Seen": l_time if status not in ["DNS", "Race Started"] else "",
            "Race Time": el_str if status not in ["DNS", "Race Started"] else "",
            "Avg Speed": avg_pace if status not in ["DNS", "Race Started", "DNF"] else 0.0,
            "Next Expected": eta_display if status not in ["Finished!", "DNF", "DNS"] else "---",
            "SortSeconds": el_sec if el_sec is not None else 999999,
            "Lap": loop if status not in ["DNS", "Race Started"] else ""
        })
    
    full_df = pd.DataFrame(results).sort_values(by=['SortWeight', 'SortSeconds'], ascending=[False, True])
    active_mask = full_df['SortWeight'] >= 0
    full_df.loc[active_mask, 'Pos'] = range(1, active_mask.sum() + 1)
    return full_df

# --- UI (Remains largely the same) ---
now = datetime.datetime.now()

try:
    st.image("Riverlands Logo.jpg", width=250)
except:
    st.image("logo.jpg", width=250)

st.title("Riverlands 100 Live Leaderboard")

with st.container():
    if now < START_TIME:
        st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
        st.write("**Hours Until Race Day!**")
    else:
        elapsed_diff = now - START_TIME
        display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
        st.subheader(f"⏱️ {format_delta_hhh(display_elapsed)}")
        st.write("**Elapsed Race Time**")

st.info("**Disclaimer:** Independent project. Not official race data.")

view_mode = st.radio("Select Category:", ["100 Miler", "Relay"], horizontal=True)
query = st.text_input("Search Name or Bib", placeholder="Search...") if view_mode == "100 Miler" else ""

try:
    master_df = load_data(view_mode, now)
    display_df = master_df if not query else master_df[master_df.apply(lambda r: fuzzy_match(query, r['Team/Runner']) or query in str(r['Bib']), axis=1)]

    st.dataframe(
        display_df.drop(columns=['SortWeight', 'SortSeconds']),
        column_config={
            "Pos": st.column_config.Column(alignment="right"),
            "Bib": st.column_config.Column(alignment="right"),
            "Status": st.column_config.Column(alignment="right"),
            "Miles": st.column_config.NumberColumn("Total Miles", format="%.1f", alignment="right"),
            "Avg Speed": st.column_config.NumberColumn("Avg Speed", format="%.2f mph", alignment="right"),
            "Next Expected": st.column_config.Column("Next Expected Location", alignment="right"),
            "Race Time": st.column_config.Column(alignment="right"),
            "Last Seen": st.column_config.Column(alignment="right"),
            "Lap": st.column_config.Column(alignment="right")
        },
        use_container_width=True, hide_index=True
    )
except Exception as e:
    st.error(f"Waiting for live data feed... ({e})")
