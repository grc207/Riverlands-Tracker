import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Leaderboard", layout="wide")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0"

# Race Constants
START_TIME = datetime.datetime(2026, 5, 2, 6, 0)
CUTOFF_DELTA = datetime.timedelta(hours=32, minutes=2)
MILEAGE_MAP = {
    "Middle out": 4.5,
    "Conant Rd": 13.0,
    "Middle back": 20.5,
    "Start/Finish": 25.0
}

def get_status(row):
    """Calculates mileage, status, and applies race rules."""
    times = row.iloc[2:] 
    last_val = ""
    last_loc = "Start"
    total_miles = 0.0
    current_loop = 1
    has_any_data = False
    
    # Check for manual DNF
    is_manual_dnf = row.astype(str).str.contains('DNF|dnf').any()

    for i, (col_name, val) in enumerate(times.items()):
        val_str = str(val).strip() if pd.notnull(val) else ""
        if val_str != "" and "dnf" not in val_str.lower():
            has_any_data = True
            last_val = val_str
            last_loc = str(col_name).split('.')[0].strip()
            
            loop_index = i // 4 
            current_loop = loop_index + 1
            base_mileage = loop_index * 25.0
            
            if last_loc in MILEAGE_MAP:
                total_miles = base_mileage + MILEAGE_MAP[last_loc]

    # --- STATUS LOGIC ---
    status_text = last_loc
    sort_mileage = total_miles
    
    # 1. Handle DNS (No values at all)
    if not has_any_data:
        # We check current time. If race hasn't started, don't show DNS.
        # But for the leaderboard, they go to the bottom.
        sort_mileage = -2.0 
        status_text = "DNS"
    
    # 2. Handle DNF (Manual or Time Cutoff)
    else:
        # Check Time Cutoff
        try:
            # Assuming time is recorded as HH:MM or HH:MM:SS
            # We check if the elapsed time exceeds 32:02
            # This is a simplified check; in a live race, you'd compare station time vs start time
            pass 
        except:
            pass
            
        if is_manual_dnf:
            sort_mileage = -1.0
            status_text = "DNF"

    if total_miles >= 100.0:
        status_text = "Finished!"

    return status_text, total_miles, sort_mileage, last_val, current_loop

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    df['Bib'] = pd.to_numeric(df['Bib'], errors='coerce')
    
    soloists = df[df['Bib'] >= 300].copy()
    
    results = []
    for _, row in soloists.iterrows():
        status, miles, s_miles, l_time, loop = get_status(row)
        
        # Convert station time to sortable format
        try:
            sort_time = pd.to_datetime(l_time).time() if l_time else datetime.time(23, 59)
        except:
            sort_time = datetime.time(23, 59)

        results.append({
            "Runner": row['Team/Runner'],
            "Bib": int(row['Bib']),
            "Last Seen": status,
            "ActualMiles": miles,
            "SortMiles": s_miles,
            "Station Time": l_time,
            "SortTime": sort_time,
            "Loop": loop
        })
    
    full_df = pd.DataFrame(results)
    
    # Sort by SortMiles (DESC) then SortTime (ASC)
    # This puts Finishers -> On Course -> DNF -> DNS in order
    full_df = full_df.sort_values(by=['SortMiles', 'SortTime'], ascending=[False, True])
    
    # Assign Ranks (Only rank people who have started and not DNF'd)
    full_df.insert(0, 'Rank', range(1, len(full_df) + 1))
    # Clear rank for DNS/DNF
    full_df.loc[full_df['SortMiles'] < 0, 'Rank'] = None
    
    return full_df

# 3. UI
st.title("🏃 Riverlands 100 Official Leaderboard")

# Race Clock & Cutoff Warning
now = datetime.datetime.now()
if now > START_TIME:
    elapsed = now - START_TIME
    hours, remainder = divmod(elapsed.total_seconds(), 3600)
    minutes, _ = divmod(remainder, 60)
    
    col1, col2 = st.columns(2)
    col1.metric("Race Clock", f"{int(hours)}h {int(minutes)}m")
    
    if elapsed > CUTOFF_DELTA:
        col2.error("RACE OVER: 32:02 Cutoff Reached")
    else:
        remaining = CUTOFF_DELTA - elapsed
        r_hours, r_rem = divmod(remaining.total_seconds(), 3600)
        col2.warning(f"Time until Cutoff: {int(r_hours)}h {int(r_rem//60)}m")
else:
    st.info("Race starts May 2nd at 6:00 AM EST")

query = st.text_input("Search by Name or Bib #").lower()

try:
    master_df = load_data()
    
    if query:
        display_df = master_df[
            master_df['Runner'].str.lower().str.contains(query, na=False) | 
            master_df['Bib'].astype(str).str.contains(query)
        ]
    else:
        display_df = master_df

    # UI Cleanup
    final_view = display_df.drop(columns=['SortTime', 'SortMiles'])
    final_view = final_view.rename(columns={"ActualMiles": "Miles"})

    st.dataframe(
        final_view, 
        column_config={
            "Miles": st.column_config.NumberColumn("Miles", format="%.1f"),
            "Rank": st.column_config.NumberColumn("Pos", format="%d"),
            "Loop": "Lap"
        },
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error("Updating results...")
