import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Leaderboard", layout="wide")

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
    
    if row.astype(str).str.contains('DNF|dnf').any():
        return "DNF", -1.0, "Dropped", 0 # -1 miles keeps DNFs at bottom

    for i, (col_name, val) in enumerate(times.items()):
        if pd.notnull(val) and str(val).strip() != "":
            last_val = str(val).strip()
            last_loc = str(col_name).split('.')[0].strip()
            
            loop_index = i // 4 
            current_loop = loop_index + 1
            base_mileage = loop_index * 25.0
            
            if last_loc in MILEAGE_MAP:
                total_miles = base_mileage + MILEAGE_MAP[last_loc]

    if total_miles >= 100.0:
        last_loc = "Finished!"

    return last_loc, total_miles, last_val, current_loop

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    df['Bib'] = pd.to_numeric(df['Bib'], errors='coerce')
    
    soloists = df[df['Bib'] >= 300].copy()
    
    results = []
    for _, row in soloists.iterrows():
        loc, miles, l_time, loop = get_status(row)
        
        # Create a 'Sort Time' - converts '1:30 PM' type strings to something sortable
        # If the time is empty, we set it to a very late time so they don't jump to rank 1
        try:
            sort_time = pd.to_datetime(l_time).time() if l_time else datetime.time(23, 59)
        except:
            sort_time = l_time # Fallback to string if format is weird

        results.append({
            "Runner": row['Team/Runner'],
            "Bib": int(row['Bib']),
            "Last Seen": loc,
            "Miles": miles,
            "Station Time": l_time,
            "SortTime": sort_time,
            "Loop": loop
        })
    
    full_df = pd.DataFrame(results)
    
    # --- CRITICAL SORTING ---
    # Sort by Miles DESCENDING (most miles at top)
    # Then by SortTime ASCENDING (earliest time at top)
    full_df = full_df.sort_values(by=['Miles', 'SortTime'], ascending=[False, True])
    
    # Assign Ranks
    full_df.insert(0, 'Rank', range(1, len(full_df) + 1))
    
    return full_df

# 3. UI
st.title("🏃 Riverlands 100 Live Leaderboard")

now = datetime.datetime.now()
if now > START_TIME:
    elapsed = now - START_TIME
    hours, remainder = divmod(elapsed.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    st.metric("Race Clock (Elapsed)", f"{elapsed.days}d {hours}h {minutes}m")
else:
    st.info("Race starts May 2nd at 6:00 AM EST")

query = st.text_input("Search by Name or Bib #", placeholder="Search runners...").lower()

try:
    master_df = load_data()
    
    if query:
        display_df = master_df[
            master_df['Runner'].str.lower().str.contains(query, na=False) | 
            master_df['Bib'].astype(str).str.contains(query)
        ]
    else:
        display_df = master_df

    # Drop the hidden SortTime column before displaying
    final_view = display_df.drop(columns=['SortTime'])

    st.dataframe(
        final_view, 
        column_config={
            "Miles": st.column_config.NumberColumn("Total Miles", format="%.1f"),
            "Rank": "Pos",
            "Loop": "Lap"
        },
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error("Leaderboard is updating... Check your data format if this persists.")
