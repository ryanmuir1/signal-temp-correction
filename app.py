import io
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="Sensor Current Temperature Corrector", layout="wide")

st.title("Sensor Current Temperature Corrector")
st.caption("Upload a sensor data file, filter by Bluetooth address, and compare original vs temperature-corrected CH1 current.")

CURRENT_COL_CANDIDATES = [
    "current_ch1_nanoamps",
    "current_ch1",
    "current_ch1_na",
]
TEMP_COL_CANDIDATES = [
    "temperature_case_degreecelsius",
    "temperature_case",
    "temperature_case_c",
]
TIME_COL_CANDIDATES = ["timestamp", "time", "datetime"]
ADDR_COL_CANDIDATES = ["bd_addr", "bluetooth_address", "address"]


def find_column(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


@st.cache_data
def load_file(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    content = uploaded_file.getvalue()

    if name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(content))
    else:
        text_buffer = io.BytesIO(content)
        try:
            df = pd.read_csv(text_buffer, sep=None, engine="python")
        except Exception:
            text_buffer.seek(0)
            df = pd.read_csv(text_buffer, sep="\t")

    return df


def prepare_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, str, str, str, str]:
    time_col = find_column(df, TIME_COL_CANDIDATES)
    addr_col = find_column(df, ADDR_COL_CANDIDATES)
    current_col = find_column(df, CURRENT_COL_CANDIDATES)
    temp_col = find_column(df, TEMP_COL_CANDIDATES)

    missing = []
    for label, col in {
        "timestamp": time_col,
        "bd_addr": addr_col,
        "current_ch1_nanoamps": current_col,
        "temperature_case_degreecelsius": temp_col,
    }.items():
        if col is None:
            missing.append(label)

    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(missing)
        )

    out = df.copy()
    out[time_col] = pd.to_datetime(out[time_col], errors="coerce", utc=True)
    out[current_col] = pd.to_numeric(out[current_col], errors="coerce")
    out[temp_col] = pd.to_numeric(out[temp_col], errors="coerce")
    out[addr_col] = out[addr_col].astype(str)

    out = out.dropna(subset=[time_col, current_col, temp_col, addr_col]).sort_values(time_col)

    return out, time_col, addr_col, current_col, temp_col



def add_traces(fig, data: pd.DataFrame, time_col: str, addr_col: str, current_col: str, temp_col: