import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup & Constants
st.set_page_config(page_title="Riverlands 100 Tracker", layout="wide")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0"

START_TIME = datetime.datetime(2026, 5, 2, 6, 0)
RACE_LIMIT_HOURS = 32
MAX_ALLOWED_SECONDS = (RACE_LIMIT_HOURS * 3600) + 60 + 60 # 32:02:00 failsafe
END_TIME = START_TIME + datetime.timedelta(hours=RACE_LIMIT_HOURS, minutes=2)

MAP_100 = {"Start": 0.0, "Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0}
MAP_RELAY = {"Start": 0.0, "Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0}
STATION_ORDER = ["Start", "Middle out", "Conant Rd", "Middle back", "Arrive S/F"]

def calculate_elapsed(station_time_str, current_loop, last_loc):
    if not station_time_str or str(station_time_str).strip() == "":
        return None, None, None
    try:
        clean_time = str(station_time_str).strip().split(' ')[0]
        t = pd.to_datetime(clean_time, errors='coerce').time()
        if pd.isnull(t): return None, None, None
        
        day = 2
        if current_loop >= 3 and t.hour < 14: day = 3
        if last_loc == "Finished!" and t.hour < 14: day = 3
        
        actual_dt = datetime.datetime(2026, 5, day, t.hour, t.minute)
        delta = actual_dt - START_TIME
        total_sec = int(delta.total_seconds())
        return f"{total_sec // 3600}h {(total_sec % 3600) // 60:02d}m", total_sec, actual_dt
    except:
        return None, None, None

def get_status(row, mode, now):
    mileage_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    station_counts = {"Middle out": 0, "Conant Rd": 0, "Middle back": 0, "Arrive S/F": 0}
    
    is_manual_dnf = row.astype(str).str.contains('DNF|dnf', case=False).any()
    
    # 1. FIND THE ANCHOR (The furthest column with a valid timestamp)
    furthest_col_idx = -1
    furthest_val = ""
    furthest_loc = "Start"
    furthest_occ = 0
    
    # We convert the row to a list of (column_name, value) to track index
    items = list(row.items())
    
    for i, (col_name, val) in enumerate(items):
        val_str = str(val).strip() if pd.notnull(val) else ""
        if ":" in val_str and "dnf" not in val_str.lower():
            clean_name = col_name.split('.')[0].strip()
            if "Start/Finish" in clean_name: clean_name = "Arrive S/F"
            
            if clean_name in station_counts:
                station_counts[clean_name] += 1
                furthest_col_idx = i
                furthest_val = val_str
                furthest_loc = clean_name
                furthest_occ = station_counts[clean_name]

    # 2. CALCULATE MILEAGE BASED ON ANCHOR
    if furthest_col_idx != -1:
        total_miles = ((furthest_occ - 1) * loop_dist) + mileage_map[furthest_loc]
        el_str, el_sec, actual_dt = calculate_elapsed(furthest_val, furthest_occ, furthest_loc)
        has_data = True
    else:
        total_miles = 0.0
        el_str, el_sec, actual_dt = None, None, None
        has_data = False

    # 3. STATUS LOGIC
    if total_miles >= 100.0:
        status_text = "Finished!"
    elif has_data:
        status_text = furthest_loc
    else:
        status_text = "Race Started"

    # Auto-DNF logic
    if is_manual_dnf or (now > END_TIME and status_text != "Finished!"):
        status_text = "DNF"

    return status_text, total_miles, el_str, el_sec, actual_dt, furthest_occ

@st.cache_data(ttl=20)
def load_data(mode, now):
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    
    # Find the gap
    df['is_blank'] = df['Team/Runner'].isna() | (df['Team/Runner'].astype(str).str.strip() == "")
    if df['is_blank'].any():
        gap_index = df[df['is_blank']].index[0]
        relay_df = df.loc[:gap_index-1].copy()
        miler_df = df.loc[gap_index+1:].copy()
    else:
        relay_df = df.copy()
        miler_df = pd.DataFrame()

    sub_df = miler_df if mode == "100 Miler" else relay_df
    sub_df = sub_df[sub_df['Team/Runner'].notna() & (sub_df['Team/Runner'].astype(str).str.strip() != "")]

    bib_col = [c for c in df.columns if 'Bib' in c][0]
    results = []

    for _, row in sub_df.iterrows():
        status, miles, el_str, el_sec, l_dt, loop = get_status(row, mode, now)
        
        avg_pace = miles / (el_sec / 3600) if el_sec and el_sec > 0 else 0.0
        
        results.append({
            "Pos": 0,
            "Team/Runner": row['Team/Runner'],
            "Bib": row[bib_col],
            "Status": status,
            "Total Miles": miles,
            "Last Seen": el_str if el_str else "",
            "Race Time": el_str if el_str else "",
            "Avg Speed": f"{avg_pace:.2f} mph" if avg_pace > 0 else "0.00 mph",
            "SortSeconds": el_sec if el_sec is not None else 9999999,
            "Lap": loop if miles > 0 else ""
        })
    
    if not results: return pd.DataFrame()

    full_df = pd.DataFrame(results)
    # Sort: Most miles first, then fastest time
    full_df = full_df.sort_values(by=['Total Miles', 'SortSeconds'], ascending=[False, True])
    
    active_mask = full_df['Status'] != "DNF"
    full_df.loc[active_mask, 'Pos'] = range(1, active_mask.sum() + 1)
    full_df.loc[~active_mask, 'Pos'] = None
    
    return full_df

# --- UI ---
now = datetime.datetime.now()
st.title("Riverlands 100 Live Leaderboard")

view_mode = st.radio("Select Category:", ["100 Miler", "Relay"], horizontal=True)

try:
    master_df = load_data(view_mode, now)
    if not master_df.empty:
        st.dataframe(
            master_df.drop(columns=['SortSeconds']),
            use_container_width=True, hide_index=True,
            column_config={
                "Pos": st.column_config.Column(width="small", alignment="center"),
                "Total Miles": st.column_config.NumberColumn(format="%.1f"),
                "Lap": st.column_config.Column(alignment="center")
            }
        )
    else:
        st.warning("Waiting for race data...")
except Exception as e:
    st.error(f"Display Error: {e}")
