import streamlit as st
import pandas as pd
import datetime
import time
import requests
import io

# 1. Setup
st.set_page_config(page_title="Riverlands 100 Live", layout="wide")

# 2. Force Global Cache Clear (Run on every script start)
# This ensures no old data persists in the app's memory
st.cache_data.clear()

# 3. Aggressive Loader
@st.cache_data(ttl=0) # TTL 0 means "Never Cache"
def load_live_data(buster):
    # We append a unique timestamp 't' to the URL to bypass Google's server cache
    url = f"https://docs.google.com/spreadsheets/d/e/2PACX-1vQZs0na1nSuQDRDPPHmhBLRsKW7NZ7y60cC_GdfvNdVmD6uO9y3l6jMBV12SrEP2q2GE_ZQxnHaHUhn/pub?gid=503644022&single=true&output=csv&t={buster}"
    try:
        response = requests.get(url, timeout=5)
        response.encoding = 'utf-8'
        # Skip top 2 rows to hit headers on Row 3
        return pd.read_csv(io.StringIO(response.text), skiprows=2, header=None, dtype=str, na_filter=False)
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return None

# Use the current time (down to the second) as the buster
raw_data = load_live_data(int(time.time()))

# --- Logic Placeholder (Use your existing processing functions here) ---

# 4. The "Proof of Life" Debugger
st.subheader("🛠️ Connection Status")
if raw_data is not None:
    # We display Row 4 (Index 1) so you can see the latest entry immediately
    st.success(f"Connected. Last Fetch: {datetime.datetime.now().strftime('%H:%M:%S')}")
    with st.expander("Show Raw Data from Google (Row 3 & 4)"):
        st.write("If you don't see your updates here, Google's public link is stalled.")
        st.dataframe(raw_data.head(5))
else:
    st.error("Cannot reach the spreadsheet.")

# 5. UI Elements & Refresh
if st.button("🚨 Emergency Cache Wipe & Hard Refresh"):
    st.cache_data.clear()
    st.rerun()

# Auto-reload every 20 seconds
time.sleep(20)
st.rerun()
