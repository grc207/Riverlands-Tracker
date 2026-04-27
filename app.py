def get_next_expected(status, current_station, current_miles, avg_mph, mode):
    # Rule: If Finished, DNF, or DNS, no prediction is issued
    if status in ["Finished!", "DNF", "DNS"] or avg_mph <= 0:
        return "---"
    
    m_map = MAP_100 if mode == "100 Miler" else MAP_RELAY
    loop_size = 25.0 if mode == "100 Miler" else 20.0
    
    try:
        idx = STATION_ORDER.index(current_station)
        next_idx = (idx + 1) % len(STATION_ORDER)
        next_name = STATION_ORDER[next_idx]
    except:
        next_name = STATION_ORDER[0]

    # FIX: Calculate distance to next station by comparing the station's 
    # position in the loop to the runner's current position in the loop.
    current_lap_progress = current_miles % loop_size
    next_station_progress = m_map[next_name]
    
    dist_to_next = next_station_progress - current_lap_progress
    
    # If distance is negative, it means the next station is in the NEXT lap
    if dist_to_next <= 0:
        dist_to_next += loop_size

    hours_to_next = dist_to_next / avg_mph
    # Use the current time to project the arrival
    pred_time = datetime.datetime.now() + datetime.timedelta(hours=hours_to_next)
    return f"{next_name} @ {pred_time.strftime('%I:%M %p')}"

def get_status(row, mode):
    # ... [Keep previous loop identification logic] ...
    
    # NEW: Updated Status Text with Check-in Time
    if status_text not in ["Finished!", "DNF", "DNS", "Race Started"]:
        # furthest_val contains the raw time string (e.g. "10:09")
        try:
            t_check = pd.to_datetime(furthest_val).strftime('%I:%M %p')
            display_status = f"{status_text} @ {t_check}"
        except:
            display_status = status_text
    else:
        display_status = status_text

    # ... [Rest of the logic remains the same] ...
    return display_status, max_miles, display_time, total_sec, final_loop, next_exp
