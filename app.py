import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Tracker", layout="wide")

# REPLACE THIS WITH YOUR PUBLISHED CSV URL
SHEET_CSV_URL = "YOUR_CSV_URL_HERE"

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
    # Data starts after 'Team/Runner' and 'Bib' (index 0 and 1)
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
            last_loc = col_name.split('.')[0] # Clean 'Middle out.1' to 'Middle out'
            
            # Calculate loop and mileage
            loop_index = i // 4 
            current_loop = loop_index + 1
            base_mileage = loop_index * 25.0
            
            if last_loc in MILEAGE_MAP:
                total_miles = base_mileage + MILEAGE_MAP[last_loc]

    return last_loc, total_miles, last_val, current_loop

# 2. Load Data
@st.cache_data(ttl=120) 
def load_data():
    # Adding cachebuster to URL to force fresh data from Google
    data = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    
    # Filter for 100 Milers (Bibs 300+)
    soloists = data[data['Bib'] >= 300].copy()
    
    results = []
    for _, row in soloists.iterrows():
        loc, miles, l_time, loop = get_status(row)
        results.append({
            "Runner": row['Team/Runner'],
            "Bib": int(row['Bib']),
            "Last Seen": loc,
            "Miles": miles,
            "Time": l_time,
            "Loop": loop
        })
    
    return pd.DataFrame(results)

# 3. UI Build
st.title("🏃 Riverlands 100 Live Tracker")

# Elapsed Clock
now = datetime.datetime.now()
if now > START_TIME:
    elapsed = now - START_TIME
    hours, remainder = divmod(elapsed.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    st.metric("Race Clock (Elapsed)", f"{elapsed.days}d {hours}h {minutes}m")
else:
    st.info("Race starts May 2nd at 6:00 AM EST")

# Search Bar
query = st.text_input("Search by Name or Bib #", placeholder="Ex: 305 or John").lower()

try:
    df = load_data()
    
    # Apply Search Filter
    if query:
        df = df[df['Runner'].str.lower().str.contains(query) | df['Bib'].astype(str).str.contains(query)]

    # Sort: Most Miles first, then earliest Time (using string sort for now)
    df = df.sort_values(by=['Miles', 'Time'], ascending=[False, True])
    
    # Add Rank
    df.insert(0, 'Rank', range(1, len(df) + 1))

    # Clean display for DNF
    df.loc[df['Last Seen'] == 'DNF', 'Rank'] = "-"

    # Display Table
    st.dataframe(
        df, 
        column_config={
            "Miles": st.column_config.NumberColumn("Total Miles", format="%.1f"),
            "Time": "Time at Station",
            "Rank": "Pos"
        },
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error(f"Waiting for live data... (Ensure Sheet is Published to Web as CSV)")
    st.info("Technical Detail: " + str(e))
