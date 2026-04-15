import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os

st.set_page_config(page_title="ETF Portfolio Dashboard", layout="wide")

st.title("Multi-Portfolio ETF Dashboard")
st.markdown("Track and compare your ETF portfolios: VWRL, AVSG, VUKE, SGLN, VAGP, GGRP, BCOG")

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

# Portfolio storage (using session state)
if 'portfolios' not in st.session_state:
    st.session_state.portfolios = {}

if 'current_portfolio' not in st.session_state:
    st.session_state.current_portfolio = None

# Fetch data with proper error handling
@st.cache_data(ttl=3600)
def get_etf_data(display_name, period):
    ticker = etf_mapping[display_name]
    try:
        etf = yf.Ticker(ticker)
        df = etf.history(period=period)

        if df.empty:
            return None, None

        info = etf.info if hasattr(etf, 'info') else {}
        return df, info
    except Exception as e:
        return None, None

# Sidebar - Portfolio Management
st.sidebar.header("📊 Portfolio Management")

# Create or select portfolio
portfolio_action = st.sidebar.radio("Action", ["View Portfolios", "Create New Portfolio"])

if portfolio_action == "Create New Portfolio":
    st.sidebar.subheader("Create New Portfolio")
    new_portfolio_name = st.sidebar.text_input("Portfolio Name", placeholder="My Portfolio")

    if new_portfolio_name:
        st.sidebar.write("**Add ETFs and their allocations:**")

        portfolio_holdings = {}
        total_allocation = 0

        # Dynamic input for ETF holdings
        for etf in etf_display_names:
            weight = st.sidebar.number_input(
                f"{etf} Allocation (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.5,
                key=f"weight_{etf}"
            )
            if weight > 0:
                portfolio_holdings[etf] = weight
                total_allocation += weight

        # Display allocation summary
        if portfolio_holdings:
            st.sidebar.write(f"**Total Allocation: {total_allocation:.2f}%**")

            if total_allocation == 100.0:
                st.sidebar.success("✓ Allocation complete (100%)")

                if st.sidebar.button("Save Portfolio"):
                    st.session_state.portfolios[new_portfolio_name] = portfolio_holdings
                    st.session_state.current_portfolio = new_portfolio_name
                    st.sidebar.success(f"Portfolio '{new_portfolio_name}' saved!")
                    st.rerun()
            elif total_allocation > 0:
                st.sidebar.warning(f"⚠ Current allocation: {total_allocation:.2f}% (adjust to 100%)")
            else:
                st.sidebar.info("Select at least one ETF")

else:  # View Portfolios
    st.sidebar.subheader("Your Portfolios")

    if st.session_state.portfolios:
        portfolio_names = list(st.session_state.portfolios.keys())
        selected_portfolio = st.sidebar.selectbox(
            "Select Portfolio",
            portfolio_names,
            key="portfolio_select"
        )
        st.session_state.current_portfolio = selected_portfolio

        # Portfolio actions
        col1, col2, col3 = st.sidebar.columns(3)

        with col2:
            if st.button("🗑️ Delete"):
                del st.session_state.portfolios[selected_portfolio]
                st.session_state.current_portfolio = None
                st.sidebar.success("Portfolio deleted!")
                st.rerun()

        with col1:
            if st.button("✏️ Edit"):
                st.session_state.edit_mode = True
    else:
        st.sidebar.info("No portfolios created yet. Create one to get started!")

# Time period selector
st.sidebar.header("⏱️ Dashboard Settings")
period = st.sidebar.selectbox(
    "Select Time Period",
    ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
    index=3
)

# Main content area
if st.session_state.portfolios:
    portfolio_names = list(st.session_state.portfolios.keys())

    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Portfolio Overview", 
        "Allocation", 
        "Performance Comparison", 
        "Historical Data", 
        "All ETFs"
    ])

    with tab1:
        st.subheader("Portfolio Overview")

        if st.session_state.current_portfolio:
            current_portfolio_data = st.session_state.portfolios[st.session_state.current_portfolio]

            st.write(f"### {st.session_state.current_portfolio}")

            # Portfolio composition
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Portfolio Holdings:**")
                holdings_df = pd.DataFrame(list(current_portfolio_data.items()), columns=["ETF", "Allocation (%)"])
                holdings_df = holdings_df.sort_values("Allocation (%)", ascending=False)
                st.dataframe(holdings_df, use_container_width=True, hide_index=True)

            with col2:
                st.write("**Portfolio Metrics:**")

                # Calculate portfolio metrics
                portfolio_return = 0
                portfolio_volatility = 0
                portfolio_value = 0
                etf_count = 0

                for etf, weight in current_portfolio_data.items():
                    df, _ = get_etf_data(etf, period)
                    if df is not None and not df.empty:
                        start_price = df['Close'].iloc[0]
                        end_price = df['Close'].iloc[-1]
                        etf_return = ((end_price - start_price) / start_price) * 100
                        etf_volatility = df['Close'].pct_change().std() * 100

                        portfolio_return += (etf_return * weight / 100)
                        portfolio_volatility += ((etf_volatility ** 2) * (weight / 100) ** 2)
                        etf_count += 1

                portfolio_volatility = (portfolio_volatility ** 0.5) if portfolio_volatility > 0 else 0

                # Display metrics
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    st.metric("Portfolio Return", f"{portfolio_return:.2f}%")
                with col_m2:
                    st.metric("Portfolio Volatility", f"{portfolio_volatility:.2f}%")
                with col_m3:
                    st.metric("ETF Holdings", etf_count)
        else:
            st.info("Select a portfolio to view details")

    with tab2:
        st.subheader("Portfolio Allocation")

        # Select portfolio to view
        view_portfolio = st.selectbox("Select portfolio to view allocation", portfolio_names, key="alloc_select")

        if view_portfolio:
            portfolio_data = st.session_state.portfolios[view_portfolio]

            # Pie chart
            fig = go.Figure(data=[go.Pie(
                labels=list(portfolio_data.keys()),
                values=list(portfolio_data.values()),
                hovertemplate='<b>%{label}</b><br>Allocation: %{value:.2f}%<extra></extra>'
            )])

            fig.update_layout(
                title=f"{view_portfolio} - Asset Allocation",
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)

            # Allocation table
            st.write("**Allocation Details:**")
            alloc_df = pd.DataFrame(list(portfolio_data.items()), columns=["ETF", "Allocation (%)"])
            alloc_df = alloc_df.sort_values("Allocation (%)", ascending=False)
            st.dataframe(alloc_df, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("Portfolio Performance Comparison")

        # Compare multiple portfolios
        compare_portfolios = st.multiselect(
            "Select portfolios to compare",
            portfolio_names,
            default=portfolio_names[:min(2, len(portfolio_names))]
        )

        if compare_portfolios:
            # Create comparison chart
            fig = go.Figure()

            comparison_data = []

            for portfolio_name in compare_portfolios:
                portfolio_data = st.session_state.portfolios[portfolio_name]

                # Get price data for all ETFs and weight them
                portfolio_prices = None

                for etf, weight in portfolio_data.items():
                    df, _ = get_etf_data(etf, period)

                    if df is not None and not df.empty:
                        if portfolio_prices is None:
                            portfolio_prices = df['Close'].copy() * (weight / 100)
                        else:
                            # Align indices
                            aligned_price = df['Close'].reindex(portfolio_prices.index, method='ffill')
                            portfolio_prices += aligned_price * (weight / 100)

                if portfolio_prices is not None:
                    # Normalize to 100
                    normalized = (portfolio_prices / portfolio_prices.iloc[0]) * 100

                    fig.add_trace(go.Scatter(
                        x=normalized.index,
                        y=normalized.values,
                        mode='lines',
                        name=portfolio_name,
                        hovertemplate='<b>%{fullData.name}</b><br>Date: %{x|%Y-%m-%d}<br>Value (Indexed): %{y:.2f}<extra></extra>'
                    ))

                    # Calculate return
                    total_return = ((normalized.iloc[-1] - 100) / 100) * 100
                    comparison_data.append({
                        "Portfolio": portfolio_name,
                        "Return (%)": f"{total_return:.2f}%",
                        "Starting Value": f"100.00",
                        "Ending Value": f"{normalized.iloc[-1]:.2f}"
                    })

            fig.update_layout(
                title="Portfolio Performance Comparison (Indexed to 100)",
                xaxis_title="Date",
                yaxis_title="Indexed Value",
                hovermode='x unified',
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)

            # Comparison table
            if comparison_data:
                st.write("**Performance Summary:**")
                comp_df = pd.DataFrame(comparison_data)
                st.dataframe(comp_df, use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("Historical Data")

        # Select portfolio and ETF
        col1, col2 = st.columns(2)

        with col1:
            selected_portfolio_data = st.selectbox("Select Portfolio", portfolio_names, key="hist_portfolio")

        with col2:
            portfolio_etfs = list(st.session_state.portfolios[selected_portfolio_data].keys())
            selected_etf = st.selectbox("Select ETF", portfolio_etfs, key="hist_etf")

        df, _ = get_etf_data(selected_etf, period)
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True)

            # Download button
            csv = df.to_csv()
            st.download_button(
                label=f"Download {selected_etf} Data as CSV",
                data=csv,
                file_name=f"{selected_etf}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

    with tab5:
        st.subheader("All Available ETFs")

        period_all = st.selectbox("Select Time Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], key="all_etf_period")

        # Chart all ETFs
        fig = go.Figure()

        for etf in etf_display_names:
            df, _ = get_etf_data(etf, period_all)
            if df is not None and not df.empty:
                normalized = (df['Close'] / df['Close'].iloc[0]) * 100
                fig.add_trace(go.Scatter(
                    x=normalized.index,
                    y=normalized.values,
                    mode='lines',
                    name=etf,
                    hovertemplate='<b>%{fullData.name}</b><br>Date: %{x|%Y-%m-%d}<br>Price (Indexed): %{y:.2f}<extra></extra>'
                ))

        fig.update_layout(
            title="All Available ETFs - Price Performance (Indexed to 100)",
            xaxis_title="Date",
            yaxis_title="Indexed Price",
            hovermode='x unified',
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)

        # Performance table
        st.write("**ETF Performance Metrics:**")

        perf_data = []
        for etf in etf_display_names:
            df, _ = get_etf_data(etf, period_all)
            if df is not None and not df.empty:
                start_price = df['Close'].iloc[0]
                end_price = df['Close'].iloc[-1]
                return_pct = ((end_price - start_price) / start_price) * 100
                volatility = df['Close'].pct_change().std() * 100

                perf_data.append({
                    "ETF": etf,
                    "Current Price (GBp)": f"{end_price:.2f}",
                    "Return (%)": f"{return_pct:.2f}%",
                    "Volatility (%)": f"{volatility:.2f}%",
                    "52W High (GBp)": f"{df['High'].max():.2f}",
                    "52W Low (GBp)": f"{df['Low'].min():.2f}",
                })

        if perf_data:
            perf_df = pd.DataFrame(perf_data)
            st.dataframe(perf_df, use_container_width=True, hide_index=True)

else:
    st.info("👈 Create a portfolio to get started! Use the sidebar to create your first portfolio.")

# Footer
st
