import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup & Constants
st.set_page_config(page_title="Riverlands 100 Live Leaderboard", layout="wide")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0"

# Race Parameters
START_TIME_HOUR = 6 
RACE_LIMIT_HOURS = 32

# Station Mile Maps
MAP_100 = {"Start": 0.0, "Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0, "Start/Finish": 25.0}
MAP_RELAY = {"Start": 0.0, "Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0, "Start/Finish": 20.0}

def get_status(row, mode):
    mileage_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    
    max_miles = 0.0
    furthest_val = ""
    furthest_station = "Start"
    max_loop = 1
    
    # Iterate through row items. col_name contains the Pandas-suffixed header (e.g., 'Arrive S/F.4')
    for col_name, val in row.items():
        val_str = str(val).strip() if pd.notnull(val) else ""
        
        # Human entry check: Must contain a time (:) and not be a DNF note
        if ":" in val_str and "dnf" not in val_str.lower():
            base_header = col_name.split('.')[0].strip()
            if "Start/Finish" in base_header: base_header = "Arrive S/F"

            if base_header in mileage_map:
                # LAP DETERMINATION: Using Pandas suffix (.1, .2) to identify lap
                try:
                    lap_num = int(col_name.split('.')[-1]) + 1 if "." in col_name else 1
                except:
                    lap_num = 1
                
                curr_miles = ((lap_num - 1) * loop_dist) + mileage_map[base_header]
                
                # Update High Water Mark - ensures missing cells don't stop progress
                if curr_miles >= max_miles:
                    max_miles = curr_miles
                    furthest_val = val_str
                    furthest_station = "Arrive S/F" if "Finish" in base_header else base_header
                    max_loop = lap_num

    if max_miles == 0.0:
        # Check for DNS/Started but no time entered yet
        return "Race Started", 0.0, "", 0, 1

    # 2 PM FIXED WINDOW LOGIC (Primitive Power Rule)
    try:
        t_parsed = pd.to_datetime(furthest_val, errors='coerce').time()
        sec = t_parsed.hour * 3600 + t_parsed.minute * 60
        
        # Same Day if >= 2PM; Next Day if < 2PM
        if t_parsed.hour >= 14:
            total_sec = sec - (START_TIME_HOUR * 3600)
        else:
            total_sec = (sec + 86400) - (START_TIME_HOUR * 3600)
            
        h, m = divmod(total_sec // 60, 60)
        time_str = f"{int(h)}h {int(m):02d}m"
    except:
        time_str, total_sec = "---", 999999

    # Final status text
    status_text = "Finished!" if max_miles >= 100.0 else furthest_station
    
    # Manual DNF or exceeding 32 hours flip
    if row.astype(str).str.contains('DNF|dnf', case=False).any() or (total_sec > RACE_LIMIT_HOURS * 3600 and status_text != "Finished!"):
        status_text = "DNF"

    return status_text, max_miles, time_str, total_sec, max_loop

@st.cache_data(ttl=15)
def load_data(mode):
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    
    # 1. SPLIT DATA based on the blank row separator
    df['is_blank'] = df['Team/Runner'].isna() | (df['Team/Runner'].astype(str).str.strip() == "")
    if df['is_blank'].any():
        gap = df[df['is_blank']].index[0]
        relay_df, miler_df = df.loc[:gap-1].copy(), df.loc[gap+1:].copy()
    else:
        relay_df, miler_df = df.copy(), pd.DataFrame()

    active_df = miler_df if mode == "100 Miler" else relay_df
    active_df = active_df[active_df['Team/Runner'].notna() & (active_df['Team/Runner'].astype(str).str.strip() != "")]
    
    bib_col = [c for c in df.columns if 'Bib' in c][0]
    results = []

    for _, row in active_df.iterrows():
        status, miles, t_disp, t_sec, loop = get_status(row, mode)
        avg_pace = miles / (t_sec / 3600) if t_sec > 0 else 0.0
        
        results.append({
            "Pos": 0,
            "Team/Runner": row['Team/Runner'],
            "Bib": row[bib_col],
            "Status": status,
            "Total Miles": miles,
            "Race Time": t_disp,
            "Avg Speed": f"{avg_pace:.2f} mph" if avg_pace > 0 else "0.00 mph",
            "SortSeconds": t_sec,
            "Lap": loop if miles > 0 else ""
        })
    
    if not results: return pd.DataFrame()

    # 2. STRICT SORTING LOGIC
    # Sort by Miles (Descending) then Race Time (Ascending)
    full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'SortSeconds'], ascending=[False, True])
    
    # 3. POSITION ASSIGNMENT
    # Only assign numbers to non-DNF participants who have actual mileage recorded
    mask = (full_df['Status'] != "DNF") & (full_df['Total Miles'] > 0)
    full_df.loc[mask, 'Pos'] = range(1, mask.sum() + 1)
    full_df.loc[~mask, 'Pos'] = None
    
    return full_df

# --- Main App ---
st.title("Riverlands 100 Live Leaderboard")
view_mode = st.radio("Select Category:", ["100 Miler", "Relay"], horizontal=True)

try:
    master_df = load_data(view_mode)
    if not master_df.empty:
        # Display the table, dropping the hidden sorting helper column
        st.dataframe(
            master_df.drop(columns=['SortSeconds']),
            use_container_width=True, hide_index=True,
            column_config={
                "Pos": st.column_config.Column(width="small", alignment="center"),
                "Total Miles": st.column_config.NumberColumn(format="%.1f"),
                "Lap": st.column_config.Column(alignment="center"),
                "Avg Speed": st.column_config.Column(alignment="right")
            }
        )
    else:
        st.info("Searching for race data...")
except Exception as e:
    st.error(f"Display Error: {e}")

st.markdown("---")
st.caption(f"Last updated: {datetime.datetime.now().strftime('%I:%M:%S %p')} | All times based on 6:00 AM start.")
