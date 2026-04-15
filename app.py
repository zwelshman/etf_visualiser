import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="ETF Dashboard", layout="wide")

st.title("Multi-ETF Dashboard")
st.markdown("Track your favorite ETFs: VWRL, AVSG, VUKE, SGLN, VAGP, GGRP, BCOG")

# ETF list with proper ticker formats for yfinance
etf_mapping = {
    "VWRL": "VWRL.L",      # LSE
    "AVSG": "AVSG.L",      # LSE
    "VUKE": "VUKE.L",      # LSE
    "SGLN": "SGLN.L",      # LSE
    "VAGP": "VAGP.L",      # LSE
    "GGRP": "GGRP.L",      # LSE
    "BCOG": "BCOG.L"       # LSE
}

etf_display_names = list(etf_mapping.keys())

# Sidebar controls
st.sidebar.header("Dashboard Settings")
period = st.sidebar.selectbox(
    "Select Time Period",
    ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
    index=3
)

selected_etfs = st.sidebar.multiselect(
    "Select ETFs to Display",
    etf_display_names,
    default=etf_display_names
)

if not selected_etfs:
    st.warning("Please select at least one ETF")
    st.stop()

# Fetch data with proper error handling
@st.cache_data(ttl=3600)
def get_etf_data(display_name, period):
    ticker = etf_mapping[display_name]
    try:
        etf = yf.Ticker(ticker)
        df = etf.history(period=period)

        if df.empty:
            st.warning(f"No data found for {display_name} ({ticker})")
            return None, None

        info = etf.info if hasattr(etf, 'info') else {}
        return df, info
    except Exception as e:
        st.error(f"Error fetching {display_name} ({ticker}): {e}")
        return None, None

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["Price Charts", "Performance", "Data Table", "ETF Info"])

with tab1:
    st.subheader("Price Performance")

    # Normalize prices to 100 for comparison
    fig = go.Figure()
    successful_etfs = []

    for display_name in selected_etfs:
        df, info = get_etf_data(display_name, period)
        if df is not None and not df.empty:
            normalized = (df['Close'] / df['Close'].iloc[0]) * 100
            fig.add_trace(go.Scatter(
                x=normalized.index,
                y=normalized.values,
                mode='lines',
                name=display_name,
                hovertemplate='<b>%{fullData.name}</b><br>Date: %{x|%Y-%m-%d}<br>Price (Indexed to 100): %{y:.2f}<extra></extra>'
            ))
            successful_etfs.append(display_name)

    if successful_etfs:
        fig.update_layout(
            title="ETF Price Performance (Indexed to 100)",
            xaxis_title="Date",
            yaxis_title="Indexed Price",
            hovermode='x unified',
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
        st.success(f"Successfully loaded: {', '.join(successful_etfs)}")
    else:
        st.error("No data available for selected ETFs")

with tab2:
    st.subheader("Performance Metrics")

    performance_data = []

    for display_name in selected_etfs:
        df, info = get_etf_data(display_name, period)
        if df is not None and not df.empty:
            start_price = df['Close'].iloc[0]
            end_price = df['Close'].iloc[-1]
            return_pct = ((end_price - start_price) / start_price) * 100

            performance_data.append({
                "ETF": display_name,
                "Start Price": f"${start_price:.2f}",
                "Current Price": f"${end_price:.2f}",
                "Return (%)": f"{return_pct:.2f}%",
                "52W High": f"${df['High'].max():.2f}",
                "52W Low": f"${df['Low'].min():.2f}",
                "Volatility (%)": f"{df['Close'].pct_change().std() * 100:.2f}%"
            })

    if performance_data:
        perf_df = pd.DataFrame(performance_data)
        st.dataframe(perf_df, use_container_width=True)
    else:
        st.error("No performance data available")

with tab3:
    st.subheader("Historical Data")

    selected_ticker = st.selectbox("Select ETF to view data", selected_etfs)

    df, info = get_etf_data(selected_ticker, period)
    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True)

        # Download button
        csv = df.to_csv()
        st.download_button(
            label=f"Download {selected_ticker} Data as CSV",
            data=csv,
            file_name=f"{selected_ticker}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.error(f"No data available for {selected_ticker}")

with tab4:
    st.subheader("ETF Information")

    for display_name in selected_etfs:
        with st.expander(f"{display_name} Details"):
            df, info = get_etf_data(display_name, period)
            if df is not None and not df.empty:
                # Display last price and basic stats
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Current Price (GBp)", f"{df['Close'].iloc[-1]:.2f}")
                with col2:
                    st.metric("52W High (GBp)", f"{df['High'].max():.2f}")
                with col3:
                    st.metric("52W Low (GBp)", f"{df['Low'].min():.2f}")

                # Additional info from yfinance if available
                if info:
                    st.write("**Additional Information:**")
                    for key, value in info.items():
                        if value is not None and str(value) != 'nan':
                            st.write(f"- **{key}**: {value}")
            else:
                st.info(f"Data not available for {display_name}")

# Footer
st.markdown("---")
st.markdown("""
**Disclaimer:** This dashboard is for educational purposes only. 
Data is provided by Yahoo Finance and may be delayed. 
Always consult with a financial advisor before making investment decisions.

**Note:** These ETFs are priced in GBp (British Pence) as they trade on the London Stock Exchange.
""")
