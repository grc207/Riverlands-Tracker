import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup & Centered Logo
st.set_page_config(page_title="Riverlands 100 Live Leaderboard", layout="wide")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo.jpg", use_container_width=True)
    except:
        st.write("*(Logo Placeholder: logo.jpg)*")

st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)

# 2. Timer & Countdown Logic
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
RACE_LIMIT_HOURS = 32
now = datetime.datetime.now()

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

with st.container():
    if now < START_TIME:
        st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
        st.write("**Hours Until Race Day!**")
    else:
        elapsed_diff = now - START_TIME
        display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
        st.subheader(f"⏱️ {format_delta_hhh(display_elapsed)}")
        st.write("**Elapsed Race Time**")

# 3. Restored Original Disclaimer
st.info("**Disclaimer:** This is an independent project and is not maintained by the race director. "
        "All information may not be timely or accurate and should NOT be accepted as official!\n\n"
        "Some updates may take a few minutes to refresh.")

# 4. Data Processing Logic
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0"

MAP_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0, "Start/Finish": 25.0}
MAP_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0, "Start/Finish": 20.0}

def get_status(row, mode):
    mileage_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    
    max_miles = 0.0
    furthest_val = ""
    furthest_station = "Start"
    final_loop = 1
    
    row_str = row.astype(str).str.cat()
    if ":" not in row_str:
        return "DNS", 0.0, "", 999999, 1
    
    for col_name, val in row.items():
        val_str = str(val).strip() if pd.notnull(val) else ""
        if ":" in val_str and "dnf" not in val_str.lower():
            base_header = col_name.split('.')[0].strip()
            is_finish = any(x in base_header for x in ["Start/Finish", "Arrive S/F"])
            if is_finish: base_header = "Arrive S/F"

            if base_header in mileage_map:
                try:
                    lap_idx = int(col_name.split('.')[-1]) if "." in col_name else 0
                    lap_num = lap_idx + 1
                except:
                    lap_num = 1
                
                curr_miles = ((lap_num - 1) * loop_dist) + mileage_map[base_header]
                if curr_miles > 100.0: curr_miles = 100.0
                
                if curr_miles >= max_miles:
                    max_miles = curr_miles
                    furthest_val = val_str
                    furthest_station = "Arrive S/F" if is_finish else base_header
                    final_loop = lap_num if curr_miles < 100.0 else (4 if mode == "100 Miler" else 5)

    try:
        t_parsed = pd.to_datetime(furthest_val, errors='coerce').time()
        sec = t_parsed.hour * 3600 + t_parsed.minute * 60
        total_sec = sec - (6 * 3600) if t_parsed.hour >= 14 else (sec + 86400) - (6 * 3600)
        h, m = divmod(total_sec // 60, 60)
        time_str = f"{int(h)}h {int(m):02d}m"
    except:
        time_str, total_sec = "---", 999999

    status_text = "Finished!" if max_miles >= 100.0 else furthest_station
    
    # DNF Logic: Keep mileage for sort
    if "dnf" in row_str.lower() or (total_sec > RACE_LIMIT_HOURS * 3600 and status_text != "Finished!"):
        return "DNF", max_miles, "", total_sec, final_loop
    
    return status_text, max_miles, time_str, total_sec, final_loop

@st.cache_data(ttl=10)
def load_data(mode):
    df = pd.read_csv(f"{SHEET_CSV_URL}&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    
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
        avg_pace = miles / (t_sec / 3600) if (t_sec > 0 and status not in ["DNF", "DNS"]) else 0.0
        results.append({
            "Pos": 0, "Team/Runner": row['Team/Runner'], "Bib": row[bib_col],
            "Status": status, "Total Miles": miles, "Race Time": t_disp,
            "Avg Speed": f"{avg_pace:.2f} mph" if avg_pace > 0 else "0.00 mph",
            "SortSeconds": t_sec, "Lap": loop if miles > 0 else ""
        })
    
    if not results: return pd.DataFrame()

    full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'SortSeconds'], ascending=[False, True])
    
    # FIXED SYNTAX HERE
    mask = (~full_df['Status'].isin(["DNF", "DNS"])) & (full_df['Total Miles'] > 0)
    full_df.loc[mask, 'Pos'] = range(1, mask.sum() + 1)
    full_df.loc[~mask, 'Pos'] = None
    return full_df

# 5. UI Render
view_mode = st.radio("Select Category:", ["100 Miler", "Relay"], horizontal=True)

try:
    master_df = load_data(view_mode)
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
except Exception as e:
    st.error(f"Error: {e}")
