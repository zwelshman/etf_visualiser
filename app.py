import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Suppress yfinance output
import logging
logging.getLogger('yfinance').setLevel(logging.ERROR)

st.set_page_config(page_title="ETF Portfolio Dashboard", layout="wide")

# Hide Streamlit header and footer
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("📈 Multi-Portfolio ETF Dashboard")
st.markdown("Track and compare your ETF portfolios: VWRL, AVSG, VUKE, SGLN, VAGP, GGRP, BCOG")

# Default ETF list with proper ticker formats for yfinance
default_etfs = {
    "VWRL": "VWRL.L",      # LSE
    "AVSG": "AVSG.L",      # LSE
    "VUKE": "VUKE.L",      # LSE
    "SGLN": "SGLN.L",      # LSE
    "VAGP": "VAGP.L",      # LSE
    "GGRP": "GGRP.L",      # LSE
    "BCOG": "BCOG.L"       # LSE
}

# Portfolio storage (using session state)
if 'portfolios' not in st.session_state:
    st.session_state.portfolios = {}

if 'current_portfolio' not in st.session_state:
    st.session_state.current_portfolio = None

if 'etf_cache' not in st.session_state:
    st.session_state.etf_cache = {}

if 'custom_tickers' not in st.session_state:
    st.session_state.custom_tickers = {}

# Merge default and custom tickers
def get_all_tickers():
    all_tickers = default_etfs.copy()
    all_tickers.update(st.session_state.custom_tickers)
    return all_tickers

etf_mapping = get_all_tickers()
etf_display_names = list(etf_mapping.keys())

# Optimized data fetching with better caching
@st.cache_data(ttl=3600)
def get_etf_data_cached(ticker_with_suffix, period):
    """Fetch ETF data with caching"""
    try:
        etf = yf.Ticker(ticker_with_suffix)
        df = etf.history(period=period)

        if df.empty:
            return None

        return df
    except Exception:
        return None

def get_etf_data(display_name, period):
    """Wrapper to get ETF data"""
    if display_name not in etf_mapping:
        return None

    ticker = etf_mapping[display_name]
    cache_key = f"{display_name}_{period}"

    # Check session cache first
    if cache_key not in st.session_state.etf_cache:
        df = get_etf_data_cached(ticker, period)
        st.session_state.etf_cache[cache_key] = df

    return st.session_state.etf_cache[cache_key]

def validate_ticker(ticker):
    """Validate if a ticker exists on yfinance"""
    try:
        etf = yf.Ticker(ticker)
        df = etf.history(period="1d")
        return not df.empty
    except Exception:
        return False

def get_ticker_info(ticker):
    """Get basic information about a ticker from yfinance"""
    try:
        etf = yf.Ticker(ticker)
        info = etf.info
        return {
            "name": info.get("longName", ticker),
            "currency": info.get("currency", "N/A"),
            "exchange": info.get("exchange", "N/A"),
            "asset_type": info.get("quoteType", "N/A")
        }
    except Exception:
        return None

def calculate_annualized_return(start_price, end_price, num_years):
    """Calculate annualized return (CAGR)"""
    if num_years <= 0 or start_price <= 0:
        return 0
    return ((end_price / start_price) ** (1 / num_years) - 1) * 100

def get_years_from_period(period):
    """Convert period string to approximate years"""
    period_map = {
        "1mo": 1/12,
        "3mo": 3/12,
        "6mo": 6/12,
        "1y": 1,
        "2y": 2,
        "5y": 5,
        "max": 10  # Default assumption for max
    }
    return period_map.get(period, 1)

def calculate_portfolio_metrics(portfolio_data, period):
    """Calculate metrics for a portfolio efficiently"""
    portfolio_return = 0
    portfolio_annualized_return = 0
    portfolio_volatility = 0
    etf_count = 0

    # Get number of years for annualized return calculation
    num_years = get_years_from_period(period)

    for etf, weight in portfolio_data.items():
        df = get_etf_data(etf, period)
        if df is not None and not df.empty:
            start_price = df['Close'].iloc[0]
            end_price = df['Close'].iloc[-1]
            etf_return = ((end_price - start_price) / start_price) * 100
            etf_annualized_return = calculate_annualized_return(start_price, end_price, num_years)
            etf_volatility = df['Close'].pct_change().std() * 100

            portfolio_return += (etf_return * weight / 100)
            portfolio_annualized_return += (etf_annualized_return * weight / 100)
            portfolio_volatility += ((etf_volatility ** 2) * (weight / 100) ** 2)
            etf_count += 1

    portfolio_volatility = (portfolio_volatility ** 0.5) if portfolio_volatility > 0 else 0

    return portfolio_return, portfolio_annualized_return, portfolio_volatility, etf_count

def get_portfolio_performance(portfolio_data, period):
    """Calculate weighted portfolio performance"""
    portfolio_prices = None

    for etf, weight in portfolio_data.items():
        df = get_etf_data(etf, period)

        if df is not None and not df.empty:
            if portfolio_prices is None:
                portfolio_prices = df['Close'].copy() * (weight / 100)
            else:
                # Align indices and add weighted prices
                aligned_price = df['Close'].reindex(portfolio_prices.index, method='ffill')
                portfolio_prices = portfolio_prices.add(aligned_price * (weight / 100), fill_value=0)

    return portfolio_prices

# Sidebar - Portfolio Management & Ticker Management
st.sidebar.header("📊 Portfolio & Ticker Management")

# Ticker Management Section
with st.sidebar.expander("🔧 Manage Tickers", expanded=False):
    st.write("**Available Tickers:**")

    # Display current tickers
    all_tickers = get_all_tickers()
    ticker_display = pd.DataFrame([
        {"Display Name": name, "Ticker": ticker, "Type": "Default" if name in default_etfs else "Custom"}
        for name, ticker in all_tickers.items()
    ])
    st.dataframe(ticker_display, use_container_width=True, hide_index=True)

    st.divider()

    st.write("**Add New Ticker:**")

    # Create tabs for different input methods
    add_tab1, add_tab2 = st.tabs(["Manual Entry", "Auto-Detect"])

    with add_tab1:
        st.write("*Enter ticker details manually*")
        col1, col2 = st.columns(2)

        with col1:
            display_name = st.text_input("Display Name (e.g., VOO)", placeholder="e.g., VOO", key="manual_display_name")

        with col2:
            ticker_symbol = st.text_input("Ticker Symbol (e.g., VOO or VOO.US)", placeholder="e.g., VOO", key="manual_ticker_symbol")

        if display_name and ticker_symbol:
            if st.button("Add Ticker", key="manual_add_btn"):
                all_tickers_check = get_all_tickers()
                if display_name in all_tickers_check:
                    st.error(f"'{display_name}' already exists!")
                else:
                    # Validate ticker
                    with st.spinner(f"Validating {ticker_symbol}..."):
                        if validate_ticker(ticker_symbol):
                            st.session_state.custom_tickers[display_name] = ticker_symbol
                            st.success(f"✓ '{display_name}' ({ticker_symbol}) added successfully!")
                            st.rerun()
                        else:
                            st.error(f"✗ Ticker '{ticker_symbol}' not found. Please check and try again.")

    with add_tab2:
        st.write("*Search and auto-detect ticker information*")
        search_ticker = st.text_input("Search Ticker (e.g., VWRL, VOO, AAPL)", placeholder="Enter ticker symbol", key="search_ticker_input")

        if search_ticker:
            if st.button("Search & Import", key="search_import_btn"):
                with st.spinner(f"Searching for {search_ticker}..."):
                    if validate_ticker(search_ticker):
                        ticker_info = get_ticker_info(search_ticker)

                        if ticker_info:
                            st.write("**Ticker Information Found:**")
                            col_info1, col_info2 = st.columns(2)

                            with col_info1:
                                st.write(f"**Name:** {ticker_info['name']}")
                                st.write(f"**Exchange:** {ticker_info['exchange']}")

                            with col_info2:
                                st.write(f"**Currency:** {ticker_info['currency']}")
                                st.write(f"**Type:** {ticker_info['asset_type']}")

                            st.divider()

                            # Allow user to customize display name
                            custom_display_name = st.text_input(
                                "Display Name",
                                value=search_ticker,
                                key="auto_display_name"
                            )

                            if st.button("Confirm & Add Ticker", key="confirm_add_btn"):
                                all_tickers_check = get_all_tickers()
                                if custom_display_name in all_tickers_check:
                                    st.error(f"'{custom_display_name}' already exists!")
                                else:
                                    st.session_state.custom_tickers[custom_display_name] = search_ticker
                                    st.success(f"✓ '{custom_display_name}' ({search_ticker}) added successfully!")
                                    st.rerun()
                        else:
                            st.info("Ticker found but unable to retrieve detailed information. You can still add it manually.")
                    else:
                        st.error(f"✗ Ticker '{search_ticker}' not found on yfinance. Please check the symbol and try again.")

    st.divider()

    st.write("**Remove Ticker:**")
    custom_ticker_names = list(st.session_state.custom_tickers.keys())

    if custom_ticker_names:
        ticker_to_remove = st.selectbox("Select custom ticker to remove", custom_ticker_names)
        if st.button("Remove Ticker", key="remove_btn"):
            del st.session_state.custom_tickers[ticker_to_remove]
            # Clear cache for this ticker
            cache_keys_to_remove = [k for k in st.session_state.etf_cache.keys() if k.startswith(ticker_to_remove)]
            for key in cache_keys_to_remove:
                del st.session_state.etf_cache[key]
            st.success(f"'{ticker_to_remove}' removed!")
            st.rerun()
    else:
        st.info("No custom tickers to remove")

st.sidebar.divider()

# Create or select portfolio
all_tickers = get_all_tickers()
etf_display_names = list(all_tickers.keys())

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
                portfolio_return, portfolio_annualized_return, portfolio_volatility, etf_count = calculate_portfolio_metrics(current_portfolio_data, period)

                # Display metrics in a 2x2 grid
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.metric("Total Return", f"{portfolio_return:.2f}%")
                with col_m2:
                    st.metric("Annualized Return", f"{portfolio_annualized_return:.2f}%")

                col_m3, col_m4 = st.columns(2)
                with col_m3:
                    st.metric("Portfolio Volatility", f"{portfolio_volatility:.2f}%")
                with col_m4:
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
            num_years = get_years_from_period(period)

            for portfolio_name in compare_portfolios:
                portfolio_data = st.session_state.portfolios[portfolio_name]

                # Get weighted portfolio prices
                portfolio_prices = get_portfolio_performance(portfolio_data, period)

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

                    # Calculate returns
                    total_return = ((normalized.iloc[-1] - 100) / 100) * 100
                    annualized_return = calculate_annualized_return(100, normalized.iloc[-1], num_years)

                    comparison_data.append({
                        "Portfolio": portfolio_name,
                        "Total Return (%)": f"{total_return:.2f}%",
                        "Annualized Return (%)": f"{annualized_return:.2f}%",
                        "Starting Value": "100.00",
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

        df = get_etf_data(selected_etf, period)
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
        num_years = get_years_from_period(period_all)

        # Chart all ETFs
        fig = go.Figure()

        for etf in etf_display_names:
            df = get_etf_data(etf, period_all)
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
            df = get_etf_data(etf, period_all)
            if df is not None and not df.empty:
                start_price = df['Close'].iloc[0]
                end_price = df['Close'].iloc[-1]
                total_return = ((end_price - start_price) / start_price) * 100
                annualized_return = calculate_annualized_return(start_price, end_price, num_years)
                etf_volatility = df['Close'].pct_change().std() * 100

                # Calculate Sharpe Ratio (assuming 0% risk-free rate)
                sharpe_ratio = (annualized_return / etf_volatility) if etf_volatility != 0 else 0

                perf_data.append({
                    "ETF": etf,
                    "Total Return (%)": f"{total_return:.2f}%",
                    "Annualized Return (%)": f"{annualized_return:.2f}%",
                    "Volatility (%)": f"{etf_volatility:.2f}%",
                    "Sharpe Ratio": f"{sharpe_ratio:.2f}"
                })

        perf_df = pd.DataFrame(perf_data)
        st.dataframe(perf_df, use_container_width=True, hide_index=True)

else:
    st.info("👈 Create a portfolio to get started!")
