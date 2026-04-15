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
    """Calculates hours and minutes from 6am start."""
    if not station_time_str or str(station_time_str).strip() == "":
        return None, None
    
    try:
        # Convert the string from the sheet to a time object
        # This handles common formats like '2:30 PM' or '14:30'
        t = pd.to_datetime(station_time_str).time()
        
        # We assume the time belongs to the race window (May 2nd or May 3rd)
        # If the time is < 6:00 AM, we assume it's the next day (May 3rd)
        day = 2 if t.hour >= 6 else 3
        actual_time = datetime.datetime(2026, 5, day, t.hour, t.minute)
        
        delta = actual_time - START_TIME
        total_seconds = int(delta.total_seconds())
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
        sort_weight = 100.0
    
    if not has_data:
        status_text, sort_weight = "DNS", -2.0
    
    # Check elapsed for cutoff DNF
    elapsed_str, elapsed_seconds = calculate_elapsed(last_val)
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
            "Elapsed": el_str,
            "SortTime": el_sec if el_sec is not None else 999999,
            "Lap": loop
        })
    
    full_df = pd.DataFrame(results).sort_values(by=['SortWeight', 'SortTime'], ascending=[False, True])
    full_df.insert(0, 'Pos', range(1, len(full_df) + 1))
    full_df.loc[full_df['SortWeight'] < 0, 'Pos'] = None
    return full_df

# 3. UI
st.title("🏃 Riverlands 100 Live Leaderboard")

# Global Race Clock
now = datetime.datetime.now()
if now > START_TIME:
    elapsed_now = now - START_TIME
    st.metric("Total Race Time", f"{int(elapsed_now.total_seconds()//3600)}h {int((elapsed_now.total_seconds()//60)%60)}m")

query = st.text_input("Search Name or Bib", placeholder="Search runners...")

try:
    master_df = load_data()
    if query:
        mask = master_df.apply(lambda r: fuzzy_match(query, r['Runner']) or query in str(r['Bib']), axis=1)
        display_df = master_df[mask]
    else:
        display_df = master_df

    # Display cleanup
    display_df = display_df.drop(columns=['SortWeight', 'SortTime'])
    
    st.dataframe(
        display_df,
        column_config={
            "Miles": st.column_config.NumberColumn("Miles", format="%.1f"),
            "Elapsed": "Race Time",
            "Station Time": "Time of Day"
        },
        use_container_width=True, hide_index=True
    )
except Exception as e:
    st.error("Leaderboard is updating...")
