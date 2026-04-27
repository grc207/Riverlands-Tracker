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
MAX_ALLOWED_SECONDS = (RACE_LIMIT_HOURS * 3600) + 60 
END_TIME = START_TIME + datetime.timedelta(hours=RACE_LIMIT_HOURS)

# --- MILEAGE CALCULATIONS ---
# 100 Miler: 4 Loops of 25.0 miles
MAP_100 = {"Start": 0.0, "Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}

# Relay: 5 Loops of 20.0 miles
MAP_RELAY = {"Start": 0.0, "Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}

# Order for ETA calculations
STATION_ORDER = ["Start", "Middle out", "Conant Rd", "Middle back", "Arrive S/F"]

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
        clean_time = str(station_time_str).strip().split(' ')[0]
        t = pd.to_datetime(clean_time).time()
        day = 2
        if current_loop >= 3 and t.hour < 14: day = 3
        if last_loc == "Finished!" and t.hour < 14: day = 3
        
        actual_dt = datetime.datetime(2026, 5, day, t.hour, t.minute)
        delta = actual_dt - START_TIME
        total_sec = int(delta.total_seconds())
        return f"{int(total_sec//3600)}h {int((total_sec%3600)//60):02d}m", total_sec, actual_dt
    except:
        return None, None, None

def get_status(row, mode, now):
    last_val, last_loc, total_miles, current_loop, has_data = "", "Start", 0.0, 1, False
    
    mileage_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    
    station_counts = {"Middle out": 0, "Conant Rd": 0, "Middle back": 0, "Arrive S/F": 0}
    is_manual_dnf = row.astype(str).str.contains('DNF|dnf').any()

    # Iterate through columns to find timestamps
    for col_name, val in row.items():
        val_str = str(val).strip() if pd.notnull(val) else ""
        if val_str == "" or "dnf" in val_str.lower() or ":" not in val_str:
            continue

        clean_name = str(col_name).split('.')[0].strip()
        if clean_name == "Start/Finish": clean_name = "Arrive S/F"

        if clean_name in station_counts:
            station_counts[clean_name] += 1
            loop_idx = station_counts[clean_name] - 1
            has_data, last_val, last_loc = True, val_str, clean_name
            current_loop = station_counts[clean_name]
            total_miles = (loop_idx * loop_dist) + mileage_map[clean_name]

    el_str, el_sec, actual_dt = calculate_elapsed(last_val, current_loop, last_loc)

    if total_miles >= 100.0 and (el_sec is not None and el_sec <= MAX_ALLOWED_SECONDS):
        status_text, sort_weight = "Finished!", 101.0
    elif has_data:
        status_text, sort_weight = last_loc, total_miles
    else:
        status_text = "DNS" if now > (START_TIME + datetime.timedelta(hours=2)) else "Race Started"
        sort_weight = -2.0

    if is_manual_dnf or (now > END_TIME and status_text != "Finished!" and status_text != "DNS"):
        status_text, sort_weight = "DNF", -1.0
    
    return status_text, total_miles, sort_weight, last_val, current_loop, el_str, el_sec, actual_dt

@st.cache_data(ttl=30)
def load_data(mode, now):
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    
    # Clean test data
    df = df[~df['Team/Runner'].astype(str).str.contains('ignore this line|Test Data', case=False, na=False)]
    
    # Identify the correct Bib column
    bib_col = [c for c in df.columns if 'Bib' in c][0]
    df['Bib_Clean'] = pd.to_numeric(df[bib_col], errors='coerce')
    
    # CATEGORY LOGIC:
    # 100 Miler = Bib 181 to 280
    # Relay = Everything else (that isn't empty)
    is_100 = (df['Bib_Clean'] >= 181) & (df['Bib_Clean'] <= 280)
    
    if mode == "100 Miler":
        sub_df = df[is_100].copy()
    else:
        sub_df = df[~is_100 & df['Team/Runner'].notna()].copy()

    results = []
    for _, row in sub_df.iterrows():
        status, miles, s_weight, l_time, loop, el_str, el_sec, l_dt = get_status(row, mode, now)
        avg_pace = miles / (el_sec / 3600) if el_sec and el_sec > 0 else 0.0
        
        eta_display = "---"
        if status not in ["Finished!", "DNF", "DNS", "Race Started"] and avg_pace > 0:
            try:
                curr_idx = STATION_ORDER.index(status)
                next_station = STATION_ORDER[0] if status == "Arrive S/F" else STATION_ORDER[curr_idx + 1]
                m_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
                dist_to_next = m_map["Middle out"] if status == "Arrive S/F" else m_map[next_station] - m_map[status]
                hours_to_next = dist_to_next / avg_pace
                arrival_dt = l_dt + datetime.timedelta(hours=hours_to_next)
                eta_display = f"{next_station} @ {arrival_dt.strftime('%I:%M %p').lstrip('0')}"
            except: eta_display = "TBD"

        results.append({
            "Pos": None if s_weight < 0 else 0,
            "Team/Runner": row['Team/Runner'],
            "Bib": int(row['Bib_Clean']) if pd.notnull(row['Bib_Clean']) else 0,
            "Status": status,
            "Total Miles": miles,
            "SortWeight": s_weight,
            "Last Seen": l_time if status not in ["DNS", "Race Started"] else "",
            "Race Time": el_str if status not in ["DNS", "Race Started"] else "",
            "Avg Speed": f"{avg_pace:.2f} mph" if avg_pace > 0 else "0.00 mph",
            "Next Expected Location": eta_display if status not in ["Finished!", "DNF", "DNS"] else "---",
            "SortSeconds": el_sec if el_sec is not None else 999999,
            "Lap": loop if status not in ["DNS", "Race Started"] else ""
        })
    
    full_df = pd.DataFrame(results).sort_values(by=['SortWeight', 'SortSeconds'], ascending=[False, True])
    active_mask = full_df['SortWeight'] >= 0
    full_df.loc[active_mask, 'Pos'] = range(1, active_mask.sum() + 1)
    return full_df

# --- UI ---
now = datetime.datetime.now()

try:
    st.image("Riverlands Logo.jpg", width=250)
except:
    pass

st.title("Riverlands 100 Live Leaderboard")

if now < START_TIME:
    st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
    st.write("**Countdown to Start**")
else:
    elapsed_diff = now - START_TIME
    display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
    st.subheader(f"⏱️ {format_delta_hhh(display_elapsed)}")
    st.write("**Elapsed Race Time**")

view_mode = st.radio("Select Category:", ["100 Miler", "Relay"], horizontal=True)
query = st.text_input("Search Name or Bib", placeholder="Search...")

try:
    master_df = load_data(view_mode, now)
    if query:
        display_df = master_df[master_df.apply(lambda r: fuzzy_match(query, r['Team/Runner']) or query in str(r['Bib']), axis=1)]
    else:
        display_df = master_df

    st.dataframe(
        display_df.drop(columns=['SortWeight', 'SortSeconds']),
        use_container_width=True, hide_index=True,
        column_config={
            "Pos": st.column_config.Column(width="small", alignment="center"),
            "Total Miles": st.column_config.NumberColumn(format="%.1f"),
            "Lap": st.column_config.Column(alignment="center")
        }
    )
except Exception as e:
    st.error(f"Error loading data: {e}")
