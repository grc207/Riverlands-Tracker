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

# 2. Timer & Countdown logic
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
        st.write("**Countdown to Race Start**")
    else:
        elapsed_diff = now - START_TIME
        display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
        st.subheader(f"⏱️ {format_delta_hhh(display_elapsed)}")
        st.write("**Elapsed Race Time**")

# 3. Disclaimer
st.info("**Disclaimer:** This is an independent project and is not maintained by the race director. "
        "All information may not be timely or accurate and should NOT be accepted as official!")

# 4. Station Mapping (Leave S/F is 0, Arrive S/F is Finish)
MAP_100 = {"Leave S/F": 0.0, "Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0, "Start/Finish": 25.0}
MAP_RELAY = {"Leave S/F": 0.0, "Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0, "Start/Finish": 20.0}
STATION_ORDER = ["Leave S/F", "Middle out", "Conant Rd", "Middle back", "Arrive S/F"]

def get_next_expected(status, current_station, current_miles, avg_mph, mode, last_time_str):
    if any(s in status for s in ["Finished!", "DNF", "DNS"]) or avg_mph <= 0 or not last_time_str:
        return "---"
    
    m_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_size = 25.0 if mode == "100 Miler" else 20.0
    
    try:
        t_parsed = pd.to_datetime(last_time_str, errors='coerce')
        # Day wrapping logic
        if t_parsed.hour < 6: base_dt = datetime.datetime(2026, 5, 3, t_parsed.hour, t_parsed.minute)
        elif t_parsed.hour >= 14: base_dt = datetime.datetime(2026, 5, 2, t_parsed.hour, t_parsed.minute)
        else: base_dt = datetime.datetime(2026, 5, 3, t_parsed.hour, t_parsed.minute)
    except: return "---"

    try:
        idx = STATION_ORDER.index(current_station)
        next_idx = (idx + 1) % len(STATION_ORDER)
        next_name = STATION_ORDER[next_idx]
    except: next_name = STATION_ORDER[1] # Default to next wood station if stuck

    dist_to_next = m_map[next_name] - m_map.get(current_station, 0)
    if dist_to_next <= 0: dist_to_next = m_map[STATION_ORDER[1]] # Loop wrap

    pred_time = base_dt + datetime.timedelta(hours=dist_to_next / avg_mph)
    return f"<b>{next_name}</b><br>{pred_time.strftime('%I:%M %p')}"

def get_status(row, mode):
    m_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    
    last_col, last_val = None, ""
    # Find the absolute final cell with data
    for col_name, val in row.items():
        v_str = str(val).strip() if pd.notnull(val) else ""
        if v_str != "":
            last_col, last_val = col_name, v_str

    if not last_col or ":" not in str(row.values) and "dnf" not in str(row.values).lower():
        return "DNS", 0.0, "", 999999, 1, "---"

    # Identify station and lap
    base_header = last_col.split('.')[0].strip()
    if "Start/Finish" in base_header: base_header = "Arrive S/F"
    
    try: lap_num = (int(last_col.split('.')[-1]) + 1) if "." in last_col else 1
    except: lap_num = 1
    
    lookup_key = base_header if base_header in m_map else "Arrive S/F"
    max_miles = ((lap_num - 1) * loop_dist) + m_map.get(lookup_key, 0)
    if max_miles > 100.0: max_miles = 100.0

    # DNF check
    is_dnf = "dnf" in last_val.lower()
    last_timestamp = ""
    if is_dnf:
        for col, val in reversed(list(row.items())):
            if ":" in str(val):
                last_timestamp = str(val); break
    else: last_timestamp = last_val if ":" in last_val else ""

    # Time/Pace
    try:
        t_parsed = pd.to_datetime(last_timestamp, errors='coerce').time()
        sec = t_parsed.hour * 3600 + t_parsed.minute * 60
        total_sec = sec - (6 * 3600) if t_parsed.hour >= 14 else (sec + 86400) - (6 * 3600)
        time_str = f"{total_sec//3600}h {(total_sec%3600)//60:02d}m"
        # Pace calculated based on where they were at the time of the last clock-in
        # For miles, we use the last_timestamp station distance, not the DNF distance
        t_miles = ((lap_num-1)*loop_dist) + m_map.get(lookup_key, 0) if not is_dnf else max_miles - m_map.get(lookup_key, 0)
        avg_mph = max_miles / (total_sec / 3600) if total_sec > 0 else 0
        time_checkin = t_parsed.strftime('%I:%M %p')
    except: time_str, total_sec, avg_mph, time_checkin = "---", 999999, 0, ""

    if max_miles >= 100.0: status_text = "Finished!"
    elif is_dnf: status_text = "DNF"
    else: status_text = f"<b>{lookup_key}</b><br>{time_checkin}"

    next_exp = get_next_expected(status_text, lookup_key, max_miles, avg_mph, mode, last_timestamp)
    return status_text, max_miles, ("" if "DNF" in status_text else time_str), total_sec, lap_num, next_exp

@st.cache_data(ttl=60)
def load_data(mode, query=""):
    df = pd.read_csv(f"https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    gap = df[df['Team/Runner'].isna() | (df['Team/Runner'].astype(str).str.strip() == "")].index[0]
    active_df = (df.loc[:gap-1] if mode == "Relay" else df.loc[gap+1:]).copy()
    
    bib_col = [c for c in df.columns if 'Bib' in c][0]
    if query: active_df = active_df[active_df['Team/Runner'].astype(str).str.contains(query, case=False) | active_df[bib_col].astype(str).str.contains(query, case=False)]
    
    results = []
    for _, row in active_df.iterrows():
        status, miles, t_disp, t_sec, loop, next_exp = get_status(row, mode)
        avg_mph = miles / (t_sec / 3600) if (t_sec > 0 and t_sec != 999999) else 0.0
        results.append({
            "Pos": 0, "Team/Runner": row['Team/Runner'], "Bib": row[bib_col],
            "Status": status, "Total Miles": miles, "Race Time": t_disp,
            "Avg Speed": f"{avg_mph:.2f} mph" if avg_mph > 0 else "0.00 mph",
            "Next Expected": next_exp, "SortSeconds": t_sec, "Lap": loop
        })
    
    full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'SortSeconds'], ascending=[False, True])
    mask = (~full_df['Status'].astype(str).str.contains("DNF|DNS", na=False)) & (full_df['Total Miles'] > 0)
    full_df.loc[mask, 'Pos'] = range(1, mask.sum() + 1)
    full_df.loc[~mask, 'Pos'] = None
    return full_df

# 5. UI Render
view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search_query = st.text_input("Search Name or Bib", placeholder="Search...")

try:
    master_df = load_data(view_mode, search_query)
    if not master_df.empty:
        master_df['Pos'] = master_df['Pos'].fillna('').apply(lambda x: int(x) if x != '' else '')
        html_table = master_df.drop(columns=['SortSeconds']).to_html(escape=False, index=False)
        st.markdown("<style>table { width: 100%; border-collapse: collapse; } th { background: #f0f2f6; padding: 12px; } td { padding: 12px; border-bottom: 1px solid #eee; }</style>", unsafe_allow_html=True)
        st.write(html_table, unsafe_allow_html=True)
except Exception as e: st.error(f"Waiting for data... ({e})")
