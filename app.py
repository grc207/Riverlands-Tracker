import streamlit as st
import pandas as pd
import datetime
import time
from difflib import SequenceMatcher

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Leaderboard", layout="wide")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0"

# Race Constants
START_TIME = datetime.datetime(2026, 5, 2, 6, 0)
CUTOFF_DELTA = datetime.timedelta(hours=32, minutes=2)
MILEAGE_MAP = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Start/Finish": 25.0}

def fuzzy_match(query, target):
    query, target = str(query).lower(), str(target).lower()
    if query in target: return True 
    return SequenceMatcher(None, query, target).ratio() > 0.7 

def calculate_elapsed(station_time_str):
    """Calculates continuous elapsed time from 6am Saturday through Sunday."""
    if not station_time_str or str(station_time_str).strip() == "":
        return None, None
    
    try:
        # Parse the time string from the sheet
        t = pd.to_datetime(str(station_time_str).strip()).time()
        
        # LOGIC: If the hour is between 6:00 AM and 11:59 PM, it's Day 1 (May 2)
        # If the hour is between 12:00 AM and 2:02 PM, it's Day 2 (May 3)
        if t.hour >= 6:
            actual_dt = datetime.datetime(2026, 5, 2, t.hour, t.minute)
        else:
            actual_dt = datetime.datetime(2026, 5, 3, t.hour, t.minute)
        
        delta = actual_dt - START_TIME
        total_seconds = int(delta.total_seconds())
        
        # Format for display (e.g. 26h 15m)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        return f"{hours}h {minutes:02d}m", total_seconds
    except:
        return None, None

def get_status(row):
    times = row.iloc[2:] 
    last_val, last_loc, total_miles, current_loop, has_data = "", "Start", 0.0, 1, False
    is_manual_dnf = row.astype(str).str.contains('DNF|dnf').any()

    for i, (col_name, val) in enumerate(times.items()):
        val_str = str(val).strip() if pd.notnull(val) else ""
        if val_str != "" and "dnf" not in val_str.lower():
            has_data, last_val = True, val_str
            last_loc = str(col_name).split('.')[0].strip()
            loop_idx = i // 4
            current_loop = loop_idx + 1
            if last_loc in MILEAGE_MAP:
                total_miles = (loop_idx * 25.0) + MILEAGE_MAP[last_loc]

    status_text = last_loc
    sort_weight = total_miles
    
    if total_miles >= 100.0:
        status_text = "Finished!"
        sort_weight = 100.0 # Keep finishers at the top
    
    if not has_data:
        status_text, sort_weight = "DNS", -2.0
    
    elapsed_str, elapsed_seconds = calculate_elapsed(last_val)
    
    # Apply Cutoff DNF or Manual DNF
    if is_manual_dnf or (elapsed_seconds and elapsed_seconds > CUTOFF_DELTA.total_seconds() and total_miles < 100.0):
        status_text, sort_weight = "DNF", -1.0

    return status_text, total_miles, sort_weight, last_val, current_loop, elapsed_str, elapsed_seconds

@st.cache_data(ttl=30)
def load_data():
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    df['Bib'] = pd.to_numeric(df['Bib'], errors='coerce')
    soloists = df[df['Bib'] >= 300].copy()
    
    results = []
    for _, row in soloists.iterrows():
        status, miles, s_weight, l_time, loop, el_str, el_sec = get_status(row)
        
        results.append({
            "Runner": row['Team/Runner'],
            "Bib": int(row['Bib']),
            "Status": status,
            "Miles": miles,
            "SortWeight": s_weight,
            "Station Time": l_time,
            "Race Time": el_str,
            "SortSeconds": el_sec if el_sec is not None else 999999,
            "Lap": loop
        })
    
    # PRIMARY SORT: Miles (Descending)
    # SECONDARY SORT: SortSeconds (Ascending - faster time wins)
    full_df = pd.DataFrame(results).sort_values(by=['SortWeight', 'SortSeconds'], ascending=[False, True])
    
    full_df.insert(0, 'Pos', range(1, len(full_df) + 1))
    full_df.loc[full_df['SortWeight'] < 0, 'Pos'] = None
    return full_df

# 3. UI
st.title("🏃 Riverlands 100 Official Leaderboard")

query = st.text_input("Search Name or Bib", placeholder="Search runners...")

try:
    master_df = load_data()
    if query:
        mask = master_df.apply(lambda r: fuzzy_match(query, r['Runner']) or query in str(r['Bib']), axis=1)
        display_df = master_df[mask]
    else:
        display_df = master_df

    # Display cleanup
    final_output = display_df.drop(columns=['SortWeight', 'SortSeconds'])
    
    st.dataframe(
        final_output,
        column_config={
            "Miles": st.column_config.NumberColumn("Miles", format="%.1f"),
            "Race Time": "Elapsed",
            "Station Time": "Time of Day"
        },
        use_container_width=True, hide_index=True
    )
except Exception as e:
    st.error("Updating leaderboard...")
