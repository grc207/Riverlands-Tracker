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

# 3. Disclaimer
st.info("**Disclaimer:** This is an independent project and is not maintained by the race director. "
        "All information may not be timely or accurate and should NOT be accepted as official!\n\n"
        "Some updates may take a few minutes to refresh.")

# 4. Mapping & Helper Functions
MAP_100 = {"Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0, "Start/Finish": 25.0}
MAP_RELAY = {"Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0, "Start/Finish": 20.0}
STATION_ORDER = ["Middle out", "Conant Rd", "Middle back", "Arrive S/F"]

def get_next_expected(status, current_station, current_miles, avg_mph, mode, checkin_val):
    if any(s in status for s in ["Finished!", "DNF", "DNS"]) or avg_mph <= 0 or not checkin_val:
        return "---"
    
    m_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_size = 25.0 if mode == "100 Miler" else 20.0
    
    try:
        t_parsed = pd.to_datetime(checkin_val, errors='coerce')
        if t_parsed.hour < 6:
             base_dt = datetime.datetime(2026, 5, 3, t_parsed.hour, t_parsed.minute, t_parsed.second)
        elif t_parsed.hour >= 14:
             base_dt = datetime.datetime(2026, 5, 2, t_parsed.hour, t_parsed.minute, t_parsed.second)
        else:
             base_dt = datetime.datetime(2026, 5, 3, t_parsed.hour, t_parsed.minute, t_parsed.second)
    except:
        return "---"

    try:
        idx = STATION_ORDER.index(current_station)
        next_idx = (idx + 1) % len(STATION_ORDER)
        next_name = STATION_ORDER[next_idx]
    except:
        next_name = STATION_ORDER[0]

    current_lap_progress = current_miles % loop_size
    next_station_progress = m_map[next_name]
    dist_to_next = next_station_progress - current_lap_progress
    if dist_to_next <= 0: dist_to_next += loop_size

    hours_to_next = dist_to_next / avg_mph
    pred_time = base_dt + datetime.timedelta(hours=hours_to_next)
    return f"<b>{next_name}</b><br>{pred_time.strftime('%I:%M %p')}"

def get_status(row, mode):
    m_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    max_miles, furthest_val, furthest_station, final_loop = 0.0, "", "Start", 1
    is_dnf = False
    
    row_str = row.astype(str).str.cat()
    if ":" not in row_str and "dnf" not in row_str.lower(): 
        return "DNS", 0.0, "", 999999, 1, "---"
    
    for col_name, val in row.items():
        val_str = str(val).strip().lower() if pd.notnull(val) else ""
        if (":" in val_str) or ("dnf" in val_str):
            base_header = col_name.split('.')[0].strip()
            if any(x in base_header for x in ["Start/Finish", "Arrive S/F"]): base_header = "Arrive S/F"

            if base_header in m_map:
                try:
                    lap_num = (int(col_name.split('.')[-1]) + 1) if "." in col_name else 1
                except: lap_num = 1
                
                curr_miles = ((lap_num - 1) * loop_dist) + m_map[base_header]
                if curr_miles > 100.0: curr_miles = 100.0
                
                # Update miles if this is the furthest point reached (even if DNF)
                if curr_miles >= max_miles:
                    max_miles = curr_miles
                    furthest_station = base_header
                    final_loop = lap_num if curr_miles < 100.0 else (4 if mode == "100 Miler" else 5)
                    # If it's a timestamp, save it for pace; if it's a DNF, flag it
                    if ":" in val_str:
                        furthest_val = val_str
                        is_dnf = False # Reset if a later column has a valid time
                    if "dnf" in val_str:
                        is_dnf = True

    try:
        t_parsed = pd.to_datetime(furthest_val, errors='coerce').time()
        sec = t_parsed.hour * 3600 + t_parsed.minute * 60
        total_sec = sec - (6 * 3600) if t_parsed.hour >= 14 else (sec + 86400) - (6 * 3600)
        h, m = divmod(total_sec // 60, 60)
        time_str, avg_mph = f"{int(h)}h {int(m):02d}m", max_miles / (total_sec / 3600) if total_sec > 0 else 0
        time_checkin = t_parsed.strftime('%I:%M %p')
    except:
        time_str, total_sec, avg_mph, time_checkin = "---", 999999, 0, ""

    if max_miles >= 100.0:
        status_text = "Finished!"
    elif is_dnf or (total_sec > RACE_LIMIT_HOURS * 3600):
        status_text = "DNF"
    else:
        status_text = f"<b>{furthest_station}</b><br>{time_checkin}" if time_checkin else furthest_station

    next_exp = get_next_expected(status_text, furthest_station, max_miles, avg_mph, mode, furthest_val)
    display_time = "" if "DNF" in status_text or "DNS" in status_text else time_str

    return status_text, max_miles, display_time, total_sec, final_loop, next_exp

@st.cache_data(ttl=60)
def load_data(mode, query=""):
    df = pd.read_csv(f"https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    
    df['is_blank'] = df['Team/Runner'].isna() | (df['Team/Runner'].astype(str).str.strip() == "")
    if df['is_blank'].any():
        gap = df[df['is_blank']].index[0]
        relay_df, miler_df = df.loc[:gap-1].copy(), df.loc[gap+1:].copy()
    else: relay_df, miler_df = df.copy(), pd.DataFrame()

    active_df = miler_df if mode == "100 Miler" else relay_df
    active_df = active_df[active_df['Team/Runner'].notna()]
    
    bib_col = [c for c in df.columns if 'Bib' in c][0]
    if query:
        active_df = active_df[active_df['Team/Runner'].astype(str).str.contains(query, case=False) | active_df[bib_col].astype(str).str.contains(query, case=False)]
    
    results = []
    for _, row in active_df.iterrows():
        status, miles, t_disp, t_sec, loop, next_exp = get_status(row, mode)
        avg_pace = miles / (t_sec / 3600) if (t_sec > 0 and "DNF" not in status and "DNS" not in status) else 0.0
        results.append({
            "Pos": 0, "Team/Runner": row['Team/Runner'], "Bib": row[bib_col],
            "Status": status, "Total Miles": miles, "Race Time": t_disp,
            "Avg Speed": f"{avg_pace:.2f} mph" if avg_pace > 0 else "0.00 mph",
            "Next Expected": next_exp, "SortSeconds": t_sec, "Lap": loop if miles > 0 else ""
        })
    
    if not results: return pd.DataFrame()
    full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'SortSeconds'], ascending=[False, True])
    
    mask = (~full_df['Status'].astype(str).str.contains("DNF|DNS", na=False)) & (full_df['Total Miles'] > 0)
    full_df.loc[mask, 'Pos'] = range(1, mask.sum() + 1)
    full_df.loc[~mask, 'Pos'] = None
    return full_df

# 5. UI Render
view_mode = st.radio("Select Category:", ["100 Miler", "Relay"], horizontal=True)
search_query = st.text_input("Search Name or Bib", placeholder="Search...")

try:
    master_df = load_data(view_mode, search_query)
    if not master_df.empty:
        master_df['Pos'] = master_df['Pos'].fillna('').apply(lambda x: int(x) if x != '' else '')
        html_table = master_df.drop(columns=['SortSeconds']).to_html(escape=False, index=False)
        st.markdown(
            """
            <style>
            table { width: 100%; border-collapse: collapse; font-family: sans-serif; }
            th { background-color: #f0f2f6; text-align: left; padding: 12px; }
            td { padding: 12px; border-bottom: 1px solid #eee; vertical-align: middle; }
            tr:hover { background-color: #fafafa; }
            </style>
            """, unsafe_allow_html=True
        )
        st.write(html_table, unsafe_allow_html=True)
except Exception as e: st.error(f"Error: {e}")
