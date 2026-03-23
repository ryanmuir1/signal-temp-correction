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
]
TEMP_COL_CANDIDATES = [
    "temperature_case_degreecelsius",
]
TIME_COL_CANDIDATES = ["timestamp"]
ADDR_COL_CANDIDATES = ["bd_addr"]


def find_column(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    for cand in candidates:
        if cand in df.columns:
            return cand
    return None


@st.cache_data
def load_file(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    content = uploaded_file.getvalue()

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(content))
    return pd.read_csv(io.BytesIO(content), sep=None, engine="python")


def prepare_dataframe(df: pd.DataFrame):
    time_col = find_column(df, TIME_COL_CANDIDATES)
    addr_col = find_column(df, ADDR_COL_CANDIDATES)
    current_col = find_column(df, CURRENT_COL_CANDIDATES)
    temp_col = find_column(df, TEMP_COL_CANDIDATES)

    out = df.copy()
    out[time_col] = pd.to_datetime(out[time_col], utc=True)
    out[current_col] = pd.to_numeric(out[current_col])
    out[temp_col] = pd.to_numeric(out[temp_col])

    return out, time_col, addr_col, current_col, temp_col


def add_traces(fig, data, time_col, addr_col, current_col, temp_col, corrected=False):
    y_col = "corrected_current" if corrected else current_col

    for addr in data[addr_col].unique():
        subset = data[data[addr_col] == addr]

        fig.add_trace(
            go.Scatter(
                x=subset[time_col],
                y=subset[y_col],
                mode="lines",
                name=f"{addr} current",
            ),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=subset[time_col],
                y=subset[temp_col],
                mode="lines",
                name=f"{addr} temp",
                opacity=0.2,
                line=dict(dash="dot"),
            ),
            secondary_y=True,
        )

    fig.update_yaxes(title_text="Current (nA)", secondary_y=False)
    fig.update_yaxes(title_text="Case Temp (°C)", range=[34, 41], secondary_y=True)


uploaded_file = st.file_uploader("Upload file")

k = st.sidebar.number_input("k (per °C)", value=0.03)

if uploaded_file:
    df = load_file(uploaded_file)
    df, time_col, addr_col, current_col, temp_col = prepare_dataframe(df)

    addresses = st.multiselect("bd_addr", df[addr_col].unique(), default=df[addr_col].unique())
    df = df[df[addr_col].isin(addresses)]

    df["corrected_current"] = df[current_col] * (1 + k * (37 - df[temp_col]))

    col1, col2 = st.columns(2)

    with col1:
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        add_traces(fig1, df, time_col, addr_col, current_col, temp_col, corrected=False)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        add_traces(fig2, df, time_col, addr_col, current_col, temp_col, corrected=True)
        st.plotly_chart(fig2, use_container_width=True)
