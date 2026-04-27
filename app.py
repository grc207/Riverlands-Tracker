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
MAP_100 = {"Start": 0.0, "Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
MAP_RELAY = {"Start": 0.0, "Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}
STATION_ORDER = ["Start", "Middle out", "Conant Rd", "Middle back", "Arrive S/F"]

# --- HELPER FUNCTIONS ---

def calculate_elapsed(station_time_str, current_loop, last_loc):
    if not station_time_str or str(station_time_str).strip() == "":
        return None, None, None
    try:
        clean_time = str(station_time_str).strip().split(' ')[0]
        # Clean up cases where AM/PM might be smashed against the time
        t = pd.to_datetime(clean_time, errors='coerce').time()
        if pd.isnull(t): return None, None, None
        
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

    # Process timing columns
    for col_name, val in row.items():
        val_str = str(val).strip() if pd.notnull(val) else ""
        if val_str == "" or "dnf" in val_str.lower() or ":" not in val_str:
            continue

        clean_name = str(col_name).split('.')[0].strip()
        if "Start/Finish" in clean_name: clean_name = "Arrive S/F"

        if clean_name in station_counts:
            station_counts[clean_name] += 1
            loop_idx = station_counts[clean_name] - 1
            has_data, last_val, last_loc = True, val_str, clean_name
            current_loop = station_counts[clean_name]
            total_miles = (loop_idx * loop_dist) + mileage_map[clean_name]

    el_str, el_sec, actual_dt = calculate_elapsed(last_val, current_loop, last_loc)

    # SORT WEIGHT ASSIGNMENT
    if total_miles >= 100.0 and el_sec is not None:
        status_text, sort_weight = "Finished!", 200.0 # High weight for finish
    elif has_data:
        status_text, sort_weight = last_loc, total_miles
    else:
        status_text = "DNS" if now > (START_TIME + datetime.timedelta(hours=2)) else "Race Started"
        sort_weight = -2.0

    if is_manual_dnf:
        status_text, sort_weight = "DNF", -1.0
    
    return status_text, total_miles, sort_weight, last_val, current_loop, el_str, el_sec, actual_dt

@st.cache_data(ttl=20)
def load_data(mode, now):
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    
    # 1. Immediate Test Data Scrub
    df = df[~df['Team/Runner'].astype(str).str.contains('ignore this line|Test Data|Pos', case=False, na=False)]
    
    # 2. Strict Bib Filtering
    bib_col = [c for c in df.columns if 'Bib' in c][0]
    df['Bib_Clean'] = pd.to_numeric(df[bib_col], errors='coerce').fillna(0).astype(int)
    
    if mode == "100 Miler":
        # Strictly 181 to 280
        sub_df = df[(df['Bib_Clean'] >= 181) & (df['Bib_Clean'] <= 280)].copy()
    else:
        # Everything else that has a name and isn't a 100-miler bib
        sub_df = df[((df['Bib_Clean'] < 181) | (df['Bib_Clean'] > 280)) & (df['Team/Runner'].notna())].copy()

    results = []
    for _, row in sub_df.iterrows():
        status, miles, s_weight, l_time, loop, el_str, el_sec, l_dt = get_status(row, mode, now)
        
        # Pace/ETA
        avg_pace = miles / (el_sec / 3600) if el_sec and el_sec > 0 else 0.0
        eta_display = "---"
        if status not in ["Finished!", "DNF", "DNS", "Race Started"] and avg_pace > 0:
            try:
                curr_idx = STATION_ORDER.index(status)
                next_station = STATION_ORDER[curr_idx + 1] if status != "Arrive S/F" else "Start"
                m_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
                dist_to_next = m_map["Middle out"] if status == "Arrive S/F" else m_map[next_station] - m_map[status]
                arrival_dt = l_dt + datetime.timedelta(hours=dist_to_next / avg_pace)
                eta_display = f"{next_station} @ {arrival_dt.strftime('%I:%M %p').lstrip('0')}"
            except: pass

        results.append({
            "Pos": 0,
            "Team/Runner": row['Team/Runner'],
            "Bib": row['Bib_Clean'],
            "Status": status,
            "Total Miles": miles,
            "SortWeight": float(s_weight),
            "Last Seen": l_time if status not in ["DNS", "Race Started"] else "",
            "Race Time": el_str if status not in ["DNS", "Race Started"] else "",
            "Avg Speed": f"{avg_pace:.2f} mph" if avg_pace > 0 else "0.00 mph",
            "Next Expected Location": eta_display if status not in ["Finished!", "DNF", "DNS"] else "---",
            "SortSeconds": int(el_sec) if el_sec is not None else 999999,
            "Lap": loop if status not in ["DNS", "Race Started"] else ""
        })
    
    if not results: return pd.DataFrame()

    # Final Sort Logic
    full_df = pd.DataFrame(results)
    full_df = full_df.sort_values(by=['SortWeight', 'SortSeconds'], ascending=[False, True])
    
    # Position Logic
    active_mask = full_df['SortWeight'] >= 0
    full_df.loc[active_mask, 'Pos'] = range(1, active_mask.sum() + 1)
    full_df.loc[~active_mask, 'Pos'] = None
    
    return full_df

# --- UI (Standard Streamlit Layout) ---
now = datetime.datetime.now()
st.title("Riverlands 100 Live Leaderboard")

view_mode = st.radio("Select Category:", ["100 Miler", "Relay"], horizontal=True)

try:
    master_df = load_data(view_mode, now)
    if not master_df.empty:
        st.dataframe(
            master_df.drop(columns=['SortWeight', 'SortSeconds']),
            use_container_width=True, hide_index=True,
            column_config={"Total Miles": st.column_config.NumberColumn(format="%.1f")}
        )
    else:
        st.warning("No data found for this category.")
except Exception as e:
    st.error(f"Critical Sort Error: {e}")
