import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup and Configuration
st.set_page_config(page_title="Riverlands 100 Tracker", layout="wide")

# Direct CSV export link for your specific sheet
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0"

# Race Constants (Updated per your exact mileage specs)
START_TIME = datetime.datetime(2026, 5, 2, 6, 0)
MILEAGE_MAP = {
    "Middle out": 4.5,
    "Conant Rd": 13.0,
    "Middle back": 20.5,
    "Start/Finish": 25.0
}

def get_status(row):
    """Calculates mileage, loop, and last location based on row data."""
    # We assume Name is Col 0, Bib is Col 1. Aid stations start at Col 2.
    times = row.iloc[2:] 
    last_val = ""
    last_loc = "Start"
    total_miles = 0.0
    current_loop = 1
    
    # Check for DNF (case insensitive)
    if row.astype(str).str.contains('DNF|dnf').any():
        return "DNF", 0.0, "Dropped", 0

    # Iterate through columns to find furthest progress
    for i, (col_name, val) in enumerate(times.items()):
        if pd.notnull(val) and str(val).strip() != "":
            last_val = str(val)
            # Clean up column names (e.g., 'Middle out.1' becomes 'Middle out')
            last_loc = str(col_name).split('.')[0].strip()
            
            loop_index = i // 4 
            current_loop = loop_index + 1
            base_mileage = loop_index * 25.0
            
            if last_loc in MILEAGE_MAP:
                total_miles = base_mileage + MILEAGE_MAP[last_loc]

    return last_loc, total_miles, last_val, current_loop

# 2. Data Loading with Cache Bypassing
@st.cache_data(ttl=60) # Refreshes internal cache every minute
def load_data():
    # Adding timestamp forces Google to serve fresh data, not a cached version
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    
    # Clean headers: removes any invisible spaces or carriage returns
    df.columns = [str(c).strip() for c in df.columns]
    
    # Convert Bib to number; non-numeric rows (like headers/empty) become 'NaN'
    df['Bib'] = pd.to_numeric(df['Bib'], errors='coerce')
    
    # Filter for 100-milers (Bibs 300+)
    soloists = df[df['Bib'] >= 300].copy()
    
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

# 3. User Interface
st.title("🏃 Riverlands 100 Live Tracker")

# Race Clock Logic
now = datetime.datetime.now()
if now > START_TIME:
    elapsed = now - START_TIME
    hours, remainder = divmod(elapsed.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    st.metric("Race Clock (Elapsed)", f"{elapsed.days}d {hours}h {minutes}m")
else:
    st.info("Race starts May 2nd at 6:00 AM EST")

# Search Functionality
query = st.text_input("Search by Name or Bib #", placeholder="Ex: 305 or John").lower()

try:
    main_df = load_data()
    
    # Apply Search Filter
    if query:
        # Search against name or bib string
        main_df = main_df[main_df['Runner'].str.lower().str.contains(query, na=False) | 
                          main_df['Bib'].astype(str).str.contains(query)]

    # Sort Logic: Most Miles (Highest) first, then earliest Time (Lowest)
    main_df = main_df.sort_values(by=['Miles', 'Time'], ascending=[False, True])
    
    # Add Rank/Position column
    main_df.insert(0, 'Rank', range(1, len(main_df) + 1))

    # Output to the screen
    st.dataframe(
        main_df, 
        column_config={
            "Miles": st.column_config.NumberColumn("Total Miles", format="%.1f"),
            "Rank": "Pos",
            "Time": "Station Time",
            "Loop": "Lap"
        },
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error("Connecting to live race data...")
    # This debugging line helps us see what the script is actually 'seeing'
    try:
        debug_df = pd.read_csv(SHEET_CSV_URL)
        st.write("Headers detected in sheet:", list(debug_df.columns[:10]))
    except:
        st.write("Error: Could not reach the Google Sheet. Check 'Publish to Web' settings.")
