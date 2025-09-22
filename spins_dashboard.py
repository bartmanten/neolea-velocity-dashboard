# spins_dashboard.py — minimal sanity app
import os, sys, json, time
import streamlit as st

st.set_page_config(page_title="Neolea — sanity check", layout="wide")
st.title("✅ Streamlit is running")

st.subheader("Python & env")
st.code(f"sys.version: {sys.version}")

st.subheader("Working dir")
st.code(os.getcwd())

st.subheader("Repo files (top-level)")
st.write(sorted(os.listdir(".")))

st.subheader("Data folder listing")
data_path = "data"
if os.path.isdir(data_path):
    st.write(sorted(os.listdir(data_path)))
else:
    st.error("No 'data' folder found at app runtime.")

csv_path = os.path.join(data_path, "neolea_spins_singleperiod.csv")
st.subheader("CSV existence")
st.write(csv_path, "→", os.path.exists(csv_path))

# Try importing pandas and reading the CSV (if present)
try:
    import pandas as pd
    st.success("pandas imported OK")
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            st.success(f"CSV loaded, shape = {df.shape}")
            st.dataframe(df.head(10))
        except Exception as e:
            st.error(f"Failed to read CSV: {e}")
    else:
        st.info("CSV not found yet.")
except Exception as e:
    st.error(f"Importing pandas failed: {e!r}")
