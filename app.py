import streamlit as st
import pandas as pd
import datetime
import time

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Live Leaderboard", layout="wide")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo.jpg", use_container_width=True)
    except:
        st.write("*(Logo Placeholder: logo.jpg)*")

st.markdown("<h1 style='text-align: center;'>Riverlands 100 Live Leaderboard</h1>", unsafe_allow_html=True)

# 2. Timer
START_TIME = datetime.datetime(2026, 5, 2, 6, 0, 0)
RACE_LIMIT_HOURS = 32
now = datetime.datetime.now()

def format_delta_hhh(delta):
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"

if now < START_TIME:
    st.subheader(f"⏱️ {format_delta_hhh(START_TIME - now)}")
else:
    elapsed_diff = now - START_TIME
    display_elapsed = min(elapsed_diff, datetime.timedelta(hours=RACE_LIMIT_HOURS))
    st.subheader(f"⏱️ {format_delta_hhh(display_elapsed)}")

# 3. Mapping
MAP_100 = {"Leave S/F": 0.0, "Middle out": 4.5, "Conant Rd": 13.0, "Middle back": 20.5, "Arrive S/F": 25.0, "Start/Finish": 25.0}
MAP_RELAY = {"Leave S/F": 0.0, "Middle out": 3.5, "Conant Rd": 10.5, "Middle back": 16.5, "Arrive S/F": 20.0, "Start/Finish": 20.0}

def get_status(row, mode):
    m_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_dist = 25.0 if mode == "100 Miler" else 20.0
    
    max_miles = 0.0
    furthest_station = "Start"
    last_time_str = ""
    is_dnf = False
    current_lap = 1

    for col_name, val in row.items():
        val_str = str(val).strip().lower() if pd.notnull(val) else ""
        if val_str == "": continue

        base_header = col_name.split('.')[0].strip()
        if "Start/Finish" in base_header: base_header = "Arrive S/F"

        if base_header in m_map:
            try: lap_num = (int(col_name.split('.')[-1]) + 1) if "." in col_name else 1
            except: lap_num = 1
            
            calc_miles = ((lap_num - 1) * loop_dist) + m_map[base_header]
            
            if ":" in val_str:
                if calc_miles >= max_miles:
                    max_miles = calc_miles
                    furthest_station = base_header
                    last_time_str = val_str
                    current_lap = lap_num
            
            if "dnf" in val_str:
                if calc_miles >= max_miles:
                    max_miles = calc_miles
                    is_dnf = True
                    # We don't update last_time_str here because DNF has no time

    if max_miles == 0 and last_time_str == "":
        return "DNS", 0.0, "", 999999, 1

    # Time Math
    try:
        t_parsed = pd.to_datetime(last_time_str, errors='coerce').time()
        sec = t_parsed.hour * 3600 + t_parsed.minute * 60
        total_sec = sec - (6 * 3600) if t_parsed.hour >= 14 else (sec + 86400) - (6 * 3600)
        time_str = f"{total_sec//3600}h {(total_sec%3600)//60:02d}m"
        time_checkin = t_parsed.strftime('%I:%M %p')
    except:
        time_str, total_sec, time_checkin = "---", 999999, ""

    if max_miles >= 100.0:
        status_text = "Finished!"
    elif is_dnf:
        status_text = "DNF"
    else:
        status_text = f"<b>{furthest_station}</b><br>{time_checkin}"

    return status_text, max_miles, time_str, total_sec, current_lap

@st.cache_data(ttl=60)
def load_data(mode, query=""):
    df = pd.read_csv(f"https://docs.google.com/spreadsheets/d/1J1DJ8HGhRMa7wpl6wvbgchzGJ4cYzsfc0YZSPGbTiKU/export?format=csv&gid=0&cachebust={time.time()}")
    df.columns = [str(c).strip() for c in df.columns]
    
    mask = df['Team/Runner'].isna() | (df['Team/Runner'].astype(str).str.strip() == "")
    gap = df[mask].index[0]
    active_df = (df.loc[:gap-1] if mode == "Relay" else df.loc[gap+1:]).copy()
    
    bib_col = [c for c in df.columns if 'Bib' in c][0]
    
    # Clean Bib Decimals
    active_df[bib_col] = active_df[bib_col].astype(str).replace(r'\.0$', '', regex=True)

    if query:
        active_df = active_df[active_df['Team/Runner'].astype(str).str.contains(query, case=False) | active_df[bib_col].astype(str).contains(query, case=False)]
    
    results = []
    for _, row in active_df.iterrows():
        status, miles, t_disp, t_sec, lap = get_status(row, mode)
        
        # Strip stats for DNF/DNS
        if status in ["DNF", "DNS"]:
            avg_speed = "---"
            race_time = "---"
            lap_val = "" if status == "DNS" else lap
        else:
            avg_mph = miles / (t_sec / 3600) if (t_sec > 0 and t_sec != 999999) else 0.0
            avg_speed = f"{avg_mph:.2f} mph"
            race_time = t_disp
            lap_val = lap

        results.append({
            "Pos": 0, "Team/Runner": row['Team/Runner'], "Bib": row[bib_col],
            "Status": status, "Total Miles": miles, "Race Time": race_time,
            "Avg Speed": avg_speed, "SortSeconds": t_sec, "Lap": lap_val
        })
    
    if not results: return pd.DataFrame()
    full_df = pd.DataFrame(results).sort_values(by=['Total Miles', 'SortSeconds'], ascending=[False, True])
    
    mask_rank = (~full_df['Status'].astype(str).str.contains("DNF|DNS", na=False)) & (full_df['Total Miles'] > 0)
    full_df.loc[mask_rank, 'Pos'] = range(1, mask_rank.sum() + 1)
    full_df.loc[~mask_rank, 'Pos'] = None
    return full_df

# 5. Render
view_mode = st.radio("Category:", ["100 Miler", "Relay"], horizontal=True)
search_query = st.text_input("Search Name or Bib", placeholder="Search...")

try:
    master_df = load_data(view_mode, search_query)
    if not master_df.empty:
        master_df['Pos'] = master_df['Pos'].fillna('').apply(lambda x: int(x) if x != '' else '')
        html_table = master_df.drop(columns=['SortSeconds']).to_html(escape=False, index=False)
        st.markdown(
            """
            <style>
            table { width: 100%; border-collapse: collapse; }
            th { background-color: #f0f2f6; text-align: left; padding: 12px; }
            td { padding: 12px; border-bottom: 1px solid #eee; vertical-align: middle; }
            tr:hover { background-color: #fafafa; }
            </style>
            """, unsafe_allow_html=True
        )
        st.write(html_table, unsafe_allow_html=True)
except Exception as e:
    st.error(f"Waiting for data... ({e})")
