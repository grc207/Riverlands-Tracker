import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Tracker", layout="wide")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0"

# Race Constants
START_TIME = datetime.datetime(2026, 5, 2, 6, 0)
MILEAGE_MAP = {
    "Middle out": 4.5,
    "Conant Rd": 13.0,
    "Middle back": 20.5,
    "Start/Finish": 25.0
}

def get_status(row):
    """Calculates mileage, loop, and last location based on row data."""
    times = row.iloc[2:] 
    last_val = ""
    last_loc = "Start"
    total_miles = 0.0
    current_loop = 1
    
    # Check for DNF
    if row.astype(str).str.contains('DNF|dnf').any():
        return "DNF", 0.0, "Dropped", 0

    # Iterate through columns to find furthest progress
    for i, (col_name, val) in enumerate(times.items()):
        if pd.notnull(val) and str(val).strip() != "":
            last_val = str(val)
            last_loc = str(col_name).split('.')[0].strip()
            
            loop_index = i // 4 
            current_loop = loop_index + 1
            base_mileage = loop_index * 25.0
            
            if last_loc in MILEAGE_MAP:
                total_miles = base_mileage + MILEAGE_MAP[last_loc]

    # Change status to Finished if they complete the 4th Start/Finish
    if total_miles >= 100.0:
        last_loc = "Finished!"

    return last_loc, total_miles, last_val, current_loop

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    df['Bib'] = pd.to_numeric(df['Bib'], errors='coerce')
    
    # Filter for 100-milers
    soloists = df[df['Bib'] >= 300].copy()
    
    results = []
    for _, row in soloists.iterrows():
        loc, miles, l_time, loop = get_status(row)
        results.append({
            "Runner": row['Team/Runner'],
            "Bib": int(row['Bib']),
            "Last Seen": loc,
            "Miles": miles,
            "Station Time": l_time,
            "Loop": loop
        })
    
    full_df = pd.DataFrame(results)
    
    # --- GLOBAL SORTING & RANKING (Happens before any search) ---
    # Sort by Miles (Descending) then Station Time (Ascending)
    full_df = full_df.sort_values(by=['Miles', 'Station Time'], ascending=[False, True])
    
    # Assign actual Rank based on this global sort
    full_df.insert(0, 'Rank', range(1, len(full_df) + 1))
    
    return full_df

# 3. UI
st.title("🏃 Riverlands 100 Live Leaderboard")

# Race Clock
now = datetime.datetime.now()
if now > START_TIME:
    elapsed = now - START_TIME
    hours, remainder = divmod(elapsed.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    st.metric("Race Clock (Elapsed)", f"{elapsed.days}d {hours}h {minutes}m")
else:
    st.info("Race starts May 2nd at 6:00 AM EST")

# Search (Matches partial names/last names)
query = st.text_input("Search by Name or Bib #", placeholder="Enter bib or any part of name...").lower()

try:
    master_df = load_data()
    
    # Filter results for display based on search
    if query:
        display_df = master_df[
            master_df['Runner'].str.lower().str.contains(query, na=False) | 
            master_df['Bib'].astype(str).str.contains(query)
        ]
    else:
        display_df = master_df

    # 4. Final Display Formatting
    st.dataframe(
        display_df, 
        column_config={
            "Miles": st.column_config.NumberColumn("Total Miles", format="%.1f"),
            "Rank": "Pos",
            "Loop": "Lap"
        },
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error("Updating leaderboard...")
