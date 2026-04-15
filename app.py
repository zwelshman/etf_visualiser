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
st.markdown("Track and compare your ETF portfolios")

# Default ETFs
default_etfs = {
    "VWRL": "VWRL.L",
    "AVSG": "AVSG.L",
    "VUKE": "VUKE.L",
    "SGLN": "SGLN.L",
    "VAGP": "VAGP.L",
    "GGRP": "GGRP.L",
    "BCOG": "BCOG.L"
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

def calculate_portfolio_metrics(portfolio_data, period):
    """Calculate metrics for a portfolio efficiently"""
    portfolio_return = 0
    portfolio_volatility = 0
    etf_count = 0

    for etf, weight in portfolio_data.items():
        df = get_etf_data(etf, period)
        if df is not None and not df.empty:
            start_price = df['Close'].iloc[0]
            end_price = df['Close'].iloc[-1]
            etf_return = ((end_price - start_price) / start_price) * 100
            etf_volatility = df['Close'].pct_change().std() * 100

            portfolio_return += (etf_return * weight / 100)
            portfolio_volatility += ((etf_volatility ** 2) * (weight / 100) ** 2)
            etf_count += 1

    portfolio_volatility = (portfolio_volatility ** 0.5) if portfolio_volatility > 0 else 0

    return portfolio_return, portfolio_volatility, etf_count

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
                            suggested_display_name = ticker_info['name'][:20] if ticker_info['name'] != "N/A" else search_ticker
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
        st.sidebar.write("**Add Tickers and their allocations:**")

        portfolio_holdings = {}
        total_allocation = 0

        # Dynamic input for ticker holdings
        for ticker in etf_display_names:
            weight = st.sidebar.number_input(
                f"{ticker} Allocation (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.5,
                key=f"weight_{ticker}"
            )
            if weight > 0:
                portfolio_holdings[ticker] = weight
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
                st.sidebar.info("Select at least one ticker")

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
        "All Tickers"
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
                holdings_df = pd.DataFrame(list(current_portfolio_data.items()), columns=["Ticker", "Allocation (%)"])
                holdings_df = holdings_df.sort_values("Allocation (%)", ascending=False)
                st.dataframe(holdings_df, use_container_width=True, hide_index=True)

            with col2:
                st.write("**Portfolio Metrics:**")

                # Calculate portfolio metrics
                portfolio_return, portfolio_volatility, etf_count = calculate_portfolio_metrics(current_portfolio_data, period)

                # Display metrics
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    st.metric("Portfolio Return", f"{portfolio_return:.2f}%")
                with col_m2:
                    st.metric("Portfolio Volatility", f"{portfolio_volatility:.2f}%")
                with col_m3:
                    st.metric("Holdings Count", etf_count)
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
            alloc_df = pd.DataFrame(list(portfolio_data.items()), columns=["Ticker", "Allocation (%)"])
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

                    # Calculate return
                    total_return = ((normalized.iloc[-1] - 100) / 100) * 100
                    comparison_data.append({
                        "Portfolio": portfolio_name,
                        "Return (%)": f"{total_return:.2f}%",
                        "Starting Value": "100.00",
                        "Ending Value": f"{normalized.iloc[-1]:.2f}"
                    })

            fig.update_layout(
                title="Portfolio Performance Comparison",
                xaxis_title="Date",
                yaxis_title="Indexed Value (Starting at 100)",
                height=500,
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)

            # Comparison table
            st.write("**Performance Summary:**")
            comparison_df = pd.DataFrame(comparison_data)
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("Historical Data")

        # Select ticker to view
        selected_ticker = st.selectbox("Select ticker to view historical data", etf_display_names, key="historical_select")

        if selected_ticker:
            df = get_etf_data(selected_ticker, period)

            if df is not None and not df.empty:
                # Plot historical data
                fig = go.Figure()

                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['Close'],
                    mode='lines',
                    name='Close Price',
                    hovertemplate='<b>Date:</b> %{x|%Y-%m-%d}<br><b>Close:</b> $%{y:.2f}<extra></extra>'
                ))

                fig.update_layout(
                    title=f"{selected_ticker} - Historical Price",
                    xaxis_title="Date",
                    yaxis_title="Price",
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)

                # Display data table
                st.write("**Historical Data:**")
                display_df = df.copy()
                display_df.index = display_df.index.strftime('%Y-%m-%d')
                st.dataframe(display_df.round(2), use_container_width=True)
            else:
                st.error(f"Unable to fetch data for {selected_ticker}")

    with tab5:
        st.subheader("All Available Tickers")

        all_tickers = get_all_tickers()

        # Create a detailed ticker list
        ticker_list = []
        for name, ticker in all_tickers.items():
            ticker_type = "Default" if name in default_etfs else "Custom"
            ticker_list.append({
                "Display Name": name,
                "Ticker Symbol": ticker,
                "Type": ticker_type
            })

        ticker_df = pd.DataFrame(ticker_list)
        ticker_df = ticker_df.sort_values("Display Name")

        st.dataframe(ticker_df, use_container_width=True, hide_index=True)

        st.info(f"Total tickers available: {len(ticker_df)} (Default: {len(default_etfs)}, Custom: {len(st.session_state.custom_tickers)})")

else:
    st.info("👈 Create a portfolio to get started!")
