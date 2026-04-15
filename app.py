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
    """Returns True if query is in target OR if they are visually similar (typo tolerance)."""
    query, target = str(query).lower(), str(target).lower()
    if query in target: return True # Direct partial match
    return SequenceMatcher(None, query, target).ratio() > 0.7 # Typo tolerance

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

    # Status Logic
    status_text = last_loc
    sort_weight = total_miles
    
    # 100 Mile Finish check
    if total_miles >= 100.0:
        status_text = "Finished!"
        sort_weight = 100.0
    
    # DNS Check
    if not has_data:
        status_text, sort_weight = "DNS", -2.0
    
    # DNF Check (Manual or Clock Over 32:02)
    elapsed = datetime.datetime.now() - START_TIME
    if is_manual_dnf or (elapsed > CUTOFF_DELTA and total_miles < 100.0 and has_data):
        status_text, sort_weight = "DNF", -1.0

    return status_text, total_miles, sort_weight, last_val, current_loop

@st.cache_data(ttl=30)
def load_data():
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    df['Bib'] = pd.to_numeric(df['Bib'], errors='coerce')
    soloists = df[df['Bib'] >= 300].copy()
    
    results = []
    for _, row in soloists.iterrows():
        status, miles, s_weight, l_time, loop = get_status(row)
        try:
            sort_time = pd.to_datetime(l_time).time() if l_time else datetime.time(23, 59)
        except:
            sort_time = datetime.time(23, 59)

        results.append({
            "Runner": row['Team/Runner'],
            "Bib": int(row['Bib']),
            "Status": status,
            "Miles": miles,
            "SortWeight": s_weight,
            "Station Time": l_time,
            "SortTime": sort_time,
            "Lap": loop
        })
    
    full_df = pd.DataFrame(results).sort_values(by=['SortWeight', 'SortTime'], ascending=[False, True])
    full_df.insert(0, 'Pos', range(1, len(full_df) + 1))
    full_df.loc[full_df['SortWeight'] < 0, 'Pos'] = None
    return full_df

# UI
st.title("🏃 Riverlands 100 Live Leaderboard")

query = st.text_input("Search Name or Bib", placeholder="Try 'Partial Name' or '305'...")

try:
    master_df = load_data()
    if query:
        # Improved search logic: checks Bib OR uses fuzzy matching for names
        mask = master_df.apply(lambda r: fuzzy_match(query, r['Runner']) or query in str(r['Bib']), axis=1)
        display_df = master_df[mask]
    else:
        display_df = master_df

    st.dataframe(
        display_df.drop(columns=['SortWeight', 'SortTime']),
        column_config={"Miles": st.column_config.NumberColumn("Miles", format="%.1f")},
        use_container_width=True, hide_index=True
    )
except Exception as e:
    st.error("Updating leaderboard...")
