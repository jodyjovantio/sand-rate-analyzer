import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import io
import xlsxwriter

st.set_page_config(layout="wide")
st.title("📊 Sand Rate Analyzer (Updated)")

# ---- State initialization ----
if "zero" not in st.session_state:
    st.session_state.zero = 2000
if "step" not in st.session_state:
    st.session_state.step = 5000
if "exp" not in st.session_state:
    st.session_state.exp = 1.0

# ---- Helper Functions ----
def suggest_parameters(df):
    raw = df["raw_signal_noise"]
    zero_suggested = float(raw.min())
    step_suggested = float(max(raw.max() - raw.min(), 1))
    exp_suggested = 1.0
    return zero_suggested, step_suggested, exp_suggested

def recalculate_sandrate(df, zero, step, exp):
    df = df.copy()
    df["SandRate"] = ((df["raw_signal_noise"] - zero) / step) ** exp
    df["SandRate"] = df["SandRate"].clip(lower=0)
    return df

def generate_excel(selected_df, stats_df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format="hh:mm:ss") as writer:
        sheet = "Report"
        stats_df.to_excel(writer, sheet_name=sheet, startrow=0)

        data = selected_df[["timestamp", "SandRate", "raw_signal_noise"]].copy()
        if "flow_velocity" in selected_df.columns:
            data["flow_velocity"] = selected_df["flow_velocity"]

        data.to_excel(writer, sheet_name=sheet, startrow=7, index=False)

        workbook = writer.book
        worksheet = writer.sheets[sheet]
        time_format = workbook.add_format({"num_format": "hh:mm:ss"})
        worksheet.set_column("A:A", 20, time_format)

        chart = workbook.add_chart({"type": "line"})
        chart.add_series({
            "name": "Sand Rate",
            "categories": [sheet, 8, 0, 8 + len(data) - 1, 0],
            "values":     [sheet, 8, 1, 8 + len(data) - 1, 1],
            "line": {"color": "red"}
        })
        if "flow_velocity" in data.columns:
            chart.add_series({
                "name": "Velocity",
                "categories": [sheet, 8, 0, 8 + len(data) - 1, 0],
                "values":     [sheet, 8, 3, 8 + len(data) - 1, 3],
                "line": {"color": "gray"}
            })
        chart.add_series({
            "name": "Raw Signal",
            "categories": [sheet, 8, 0, 8 + len(data) - 1, 0],
            "values":     [sheet, 8, 2, 8 + len(data) - 1, 2],
            "line": {"color": "blue"}
        })

        chart.set_title({"name": "Sand Rate, Velocity, and Raw"})
        chart.set_x_axis({"name": "Timestamp"})
        chart.set_y_axis({"name": "Value"})
        worksheet.insert_chart("F2", chart, {"x_scale": 2, "y_scale": 1.5})
    output.seek(0)
    return output

# ---- Main App Logic ----
uploaded_files = st.file_uploader("📁 Upload one or more CSV files", type=["csv"], accept_multiple_files=True)

if uploaded_files:
    dfs = []
    for file in uploaded_files:
        try:
            df_part = pd.read_csv(file)
            dfs.append(df_part)
            st.success(f"✅ Loaded: {file.name}")
        except Exception as e:
            st.error(f"❌ Failed to read {file.name}: {e}")

    if dfs:
        df = pd.concat(dfs, ignore_index=True)

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])
        df = df.sort_values(by="timestamp")

        # ---- Apply Parameters ----
        df = recalculate_sandrate(df, st.session_state.zero, st.session_state.step, st.session_state.exp)

        # ---- Dynamic Range for Y ----
        sand_min_plot = 0
        sand_max_plot = ((df["raw_signal_noise"].max() - st.session_state.zero) / st.session_state.step) ** st.session_state.exp
        sand_max_plot = max(sand_max_plot, df["SandRate"].max())
        sand_max_plot = sand_max_plot * 1.1  # Add 10% buffer

        # ---- Plot ----
        st.markdown("### 📊 Interactive Chart")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["SandRate"],
            mode="lines", name="Sand Rate",
            line=dict(color="red"), yaxis="y1"
        ))

        if "flow_velocity" in df.columns:
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["flow_velocity"],
                mode="lines", name="Velocity",
                line=dict(color="gray"), yaxis="y1"
            ))

        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["raw_signal_noise"],
            mode="lines", name="Raw Signal",
            line=dict(color="blue"), yaxis="y2"
        ))

        fig.update_layout(
            height=500,
            margin=dict(l=40, r=40, t=30, b=40),
            xaxis=dict(title="Timestamp"),
            yaxis=dict(title="Sand Rate / Velocity",
                       tickfont=dict(color="red"),
                       range=[sand_min_plot, sand_max_plot]),
            yaxis2=dict(title="Raw Signal",
                        tickfont=dict(color="blue"),
                        anchor="x", overlaying="y", side="right",
                        range=[0, df["raw_signal_noise"].max() * 1.1]),
            legend=dict(x=0.01, y=0.99),
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)

        # ---- DEBUG RANGE DISPLAY ----
        st.markdown(f"**Sand Rate Min:** {sand_min_plot:.3f} | **Sand Rate Max:** {sand_max_plot:.3f}")

        # ---- Stats ----
        selected_df = df.copy()
        sand_stats = {
            "Maximum": f"{selected_df['SandRate'].max():.3f} g/s",
            "Minimum": f"{selected_df['SandRate'].min():.3f} g/s",
            "Average": f"{selected_df['SandRate'].mean():.3f} g/s",
            "Total": f"{selected_df['SandRate'].sum():.3f} kg"
        }
        velocity_stats = {
            "Maximum": f"{selected_df['flow_velocity'].max():.3f} m/s" if "flow_velocity" in selected_df else "NaN",
            "Minimum": f"{selected_df['flow_velocity'].min():.3f} m/s" if "flow_velocity" in selected_df else "NaN",
            "Average": f"{selected_df['flow_velocity'].mean():.3f} m/s" if "flow_velocity" in selected_df else "NaN",
            "Total": f"{selected_df['flow_velocity'].sum():.3f} m/s" if "flow_velocity" in selected_df else "NaN"
        }
        raw_stats = {
            "Maximum": f"{selected_df['raw_signal_noise'].max():.0f}",
            "Minimum": f"{selected_df['raw_signal_noise'].min():.0f}",
            "Average": f"{selected_df['raw_signal_noise'].mean():.0f}",
            "Total": f"{selected_df['raw_signal_noise'].sum():.0f}"
        }

        stats_df = pd.DataFrame({
            "Sand": sand_stats,
            "Velocity": velocity_stats,
            "Raw": raw_stats
        })
        st.table(stats_df)

        # ---- Export Excel ----
        st.download_button(
            label="⬇️ Download Result (Excel)",
            data=generate_excel(selected_df, stats_df),
            file_name="filtered_sandrate.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # ---- Recalculate ----
        st.markdown("### 🔧 Recalculate Sand Rate")
        col1, col2, col3, col4 = st.columns([1.5, 1.5, 1.5, 2])
        with col1:
            zero_input = st.number_input("Zero (offset)", value=st.session_state.zero, key="zero_input")
        with col2:
            step_input = st.number_input("Step (scale)", value=st.session_state.step, key="step_input")
        with col3:
            exp_input = st.number_input("Exp (exponent)", value=st.session_state.exp, key="exp_input")
        with col4:
            if st.button("🔁 Recalculate Now"):
                st.session_state.zero = zero_input
                st.session_state.step = step_input
                st.session_state.exp = exp_input
                st.rerun()

        if st.button("🔍 Auto Suggest Parameter"):
            suggested_zero, suggested_step, suggested_exp = suggest_parameters(df)
            st.session_state.zero = suggested_zero
            st.session_state.step = suggested_step
            st.session_state.exp = suggested_exp
            st.rerun()
