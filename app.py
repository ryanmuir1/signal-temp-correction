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



def add_traces(fig, data: pd.DataFrame, time_col: str, addr_col: str, current_col: str, temp_col: str, corrected: bool = False):
    y_col = "corrected_current" if corrected else current_col
    title_current = "Corrected CH1 Current (nA)" if corrected else "Original CH1 Current (nA)"

    for addr in data[addr_col].dropna().unique():
        subset = data[data[addr_col] == addr].sort_values(time_col)
        fig.add_trace(
            go.Scatter(
                x=subset[time_col],
                y=subset[y_col],
                mode="lines",
                name=f"{addr} current",
                legendgroup=str(addr),
                hovertemplate=(
                    "bd_addr=%{fullData.legendgroup}<br>"
                    "time=%{x}<br>"
                    f"{title_current}=%{{y:.4f}}<extra></extra>"
                ),
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=subset[time_col],
                y=subset[temp_col],
                mode="lines",
                name=f"{addr} case temp",
                legendgroup=str(addr),
                opacity=0.22,
                line={"dash": "dot"},
                hovertemplate=(
                    "bd_addr=%{fullData.legendgroup}<br>"
                    "time=%{x}<br>"
                    "Case temp=%{y:.2f} °C<extra></extra>"
                ),
            ),
            secondary_y=True,
        )

    fig.update_yaxes(title_text=title_current, secondary_y=False)
    fig.update_yaxes(title_text="Case Temperature (°C)", secondary_y=True)
    fig.update_layout(
        height=520,
        hovermode="x unified",
        legend_title_text="Trace",
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
    )


uploaded_file = st.file_uploader(
    "Upload sensor data file",
    type=["csv", "tsv", "txt", "xlsx", "xls"],
    help="Expected columns include timestamp, bd_addr, current_ch1_nanoamps, and temperature_case_degreecelsius.",
)

with st.sidebar:
    st.header("Controls")
    k_input = st.text_input(
        "Temperature correction factor, k (per °C)",
        value="0.03",
        help="Correction uses: CorrectedCurrent = CH1current × (1 + k × (37 - Tcasing)). Press Enter to update.",
    )
    reference_temp = st.number_input(
        "Reference temperature (°C)",
        value=37.0,
        step=0.1,
    )

if uploaded_file is None:
    st.info("Upload a file to begin.")
    st.stop()

try:
    raw_df = load_file(uploaded_file)
    df, time_col, addr_col, current_col, temp_col = prepare_dataframe(raw_df)
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

try:
    k = float(k_input)
except ValueError:
    st.error("k must be a valid number, for example 0.03")
    st.stop()

all_addresses = sorted(df[addr_col].dropna().unique().tolist())
default_addresses = all_addresses[: min(8, len(all_addresses))]

selected_addresses = st.multiselect(
    "Select Bluetooth addresses",
    options=all_addresses,
    default=default_addresses,
)

if not selected_addresses:
    st.warning("Select at least one Bluetooth address.")
    st.stop()

filtered = df[df[addr_col].isin(selected_addresses)].copy()
filtered["corrected_current"] = filtered[current_col] * (1 + k * (reference_temp - filtered[temp_col]))

st.subheader("Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Rows in selection", f"{len(filtered):,}")
col2.metric("Bluetooth addresses", len(selected_addresses))
col3.metric("k", f"{k:g}")
col4.metric("Reference temperature", f"{reference_temp:.1f} °C")

left, right = st.columns(2)

with left:
    st.markdown("#### Original data")
    fig_original = make_subplots(specs=[[{"secondary_y": True}]])
    add_traces(fig_original, filtered, time_col, addr_col, current_col, temp_col, corrected=False)
    st.plotly_chart(fig_original, use_container_width=True)

with right:
    st.markdown("#### Temperature-corrected data")
    fig_corrected = make_subplots(specs=[[{"secondary_y": True}]])
    add_traces(fig_corrected, filtered, time_col, addr_col, current_col, temp_col, corrected=True)
    st.plotly_chart(fig_corrected, use_container_width=True)

with st.expander("Preview filtered data"):
    preview_cols = [time_col, addr_col, current_col, temp_col, "corrected_current"]
    st.dataframe(filtered[preview_cols], use_container_width=True, height=350)
