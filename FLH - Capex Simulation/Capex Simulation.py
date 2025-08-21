import streamlit as st
import numpy as np
import pandas as pd
import altair as alt
from io import BytesIO  # <<< REQUIRED for in-memory file handling

# --- USER AUTHENTICATION ---
def check_login():
    """Returns `True` if the user is logged in."""
    if not st.session_state.get("logged_in"):
        show_login_form()
        return False
    return True

def show_login_form():
    """Displays a login form."""
    with st.form("login_form"):
        st.title("Admin Login")
        username = st.text_input("Username").lower()
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

        if submitted:
            # Check if the username exists and the password is correct
            if "credentials" in st.secrets and "usernames" in st.secrets["credentials"] and \
               username in st.secrets["credentials"]["usernames"] and \
               password == st.secrets["credentials"]["usernames"][username]["password"]:
                
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.session_state["name"] = st.secrets["credentials"]["usernames"][username]["name"]
                st.rerun() 
            else:
                st.error("Invalid username or password")

# --- MAIN APPLICATION ---
def main_app():
    # --- YOUR FULL, ORIGINAL CODE STARTS HERE ---

    # --- Page Configuration ---
    # NOTE: st.set_page_config() can only be called once per app, and must be the first Streamlit command.
    # It has been moved outside the main_app() function to the bottom of the script.

    # --- Helper Functions ---
    @st.cache_data
    def convert_df_to_csv(df):
        """Converts a DataFrame to a UTF-8 encoded CSV file for downloading."""
        return df.to_csv(index=False).encode('utf-8')

    def dfs_to_excel_bytes(df_dict):
        """
        Converts a dictionary of DataFrames to an in-memory Excel file byte stream.
        Each DataFrame becomes a sheet in the Excel file.
        """
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for sheet_name, df in df_dict.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        processed_data = output.getvalue()
        return processed_data


    st.title("Advanced Capex Outflow & Profitability Simulation")

    # --- Sidebar for Parameters ---
    with st.sidebar:
        st.header("Simulation Parameters")
        distribution_mode = st.radio(
            "Account Distribution Mode",
            ("Simulate Average", "Randomized")
        )
        num_traders = st.number_input("Number of Traders", min_value=100, max_value=1000000, value=250, step=100)
        if distribution_mode == "Simulate Average":
            avg_accounts_per_trader = st.slider("Average Accounts per Trader", min_value=1, max_value=20, value=20, step=1)
            st.slider("Randomized Account Range", min_value=1, max_value=20, value=(5, 15), step=1, disabled=True)
        else: # Randomized mode
            st.slider("Average Accounts per Trader", min_value=1, max_value=20, value=20, step=1, disabled=True)
            randomized_account_range = st.slider("Randomized Account Range", min_value=1, max_value=20, value=(5, 15), step=1)
        n_simulations = st.number_input("Number of Simulations", min_value=100, max_value=5000, value=1000, step=100)
        st.header("Financial Inputs")
        cost_per_account = st.number_input("Revenue per Account ($)", value=200, step=10)
        payout_per_successful_account = st.number_input("Payout per Successful Account ($)", value=1000, step=50)
        additional_revenue = st.number_input("Additional Revenue / Fixed Costs ($)", value=200000, step=10000)


    # --- Generate Trader Accounts based on Mode ---
    if distribution_mode == "Simulate Average":
        trader_accounts = np.random.poisson(avg_accounts_per_trader, num_traders)
    else: # Randomized mode
        trader_accounts = np.random.randint(
            low=randomized_account_range[0],
            high=randomized_account_range[1] + 1,
            size=num_traders
        )
    total_accounts = np.sum(trader_accounts)

    # --- Core Simulation & Charting Logic (Functions) ---
    @st.cache_data
    def run_vectorized_simulation(trader_accounts, n_simulations, failure_rates, payout_per_successful_account):
        results = {}
        for rate in failure_rates:
            success_rate = 1 - rate
            successful_accounts_matrix = np.random.binomial(
                n=trader_accounts, p=success_rate, size=(n_simulations, len(trader_accounts))
            )
            total_successful_accounts_per_sim = np.sum(successful_accounts_matrix, axis=1)
            payouts_for_rate = total_successful_accounts_per_sim * payout_per_successful_account
            results[rate] = payouts_for_rate
        return results

    def create_dist_chart(df: pd.DataFrame, title: str) -> alt.Chart:
        chart = alt.Chart(df).mark_bar(opacity=0.7).encode(
            alt.X('Payouts:Q', bin=alt.Bin(maxbins=50), title="Total Payout Amount"),
            y=alt.Y('count():Q', title="Frequency of Outcome"),
            tooltip=[alt.Tooltip('Payouts:Q', bin=True), 'count()']
        ).properties(title=alt.TitleParams(text=title, anchor='middle'))
        return chart

    @st.cache_data
    def run_risk_analysis(num_traders, n_simulations, failure_rates, payout_per_successful_account):
        std_devs_data = []
        avg_accounts_range = range(1, 21)
        for avg_acc in avg_accounts_range:
            trader_accounts_for_run = np.random.poisson(avg_acc, num_traders)
            sim_res = run_vectorized_simulation(trader_accounts_for_run, n_simulations, failure_rates, payout_per_successful_account)
            for rate, payouts in sim_res.items():
                std_devs_data.append({
                    'Average Accounts per Trader': avg_acc,
                    'Failure Rate': f"{int(rate * 100)}%",
                    'Standard Deviation': np.std(payouts)
                })
        return pd.DataFrame(std_devs_data)

    @st.cache_data
    def run_randomized_risk_analysis(num_traders, n_simulations, failure_rates, payout_per_successful_account):
        risk_data = []
        for max_range_val in range(2, 21):
            trader_accounts_for_run = np.random.randint(low=1, high=max_range_val + 1, size=num_traders)
            sim_res = run_vectorized_simulation(trader_accounts_for_run, n_simulations, failure_rates, payout_per_successful_account)
            for rate, payouts in sim_res.items():
                risk_data.append({
                    'Max Accounts in Range': max_range_val,
                    'Failure Rate': f"{int(rate * 100)}%",
                    'Standard Deviation': np.std(payouts)
                })
        return pd.DataFrame(risk_data)


    # --- Main App Display ---
    total_revenue = (total_accounts * cost_per_account) + additional_revenue
    st.metric("Dynamically Calculated Total Accounts", f"{total_accounts:,}")
    st.info(f"**Total Revenue Calculation:** `({total_accounts:,} accounts * ${cost_per_account}/account) + ${additional_revenue:,} = ${total_revenue:,.2f}`")


    # <<< REFACTOR: Pre-compute all data for the report and tabs >>>
    st.markdown("---")
    with st.spinner("Generating all simulation data for the report..."):
        # 1. Data for Scenario Analysis
        scenario_failure_rates = [0.90, 0.85, 0.80, 0.75, 0.50]
        simulation_results = run_vectorized_simulation(trader_accounts, n_simulations, scenario_failure_rates, payout_per_successful_account)
        
        all_scenarios_data = []
        for rate, payouts in simulation_results.items():
            for payout_value in payouts:
                all_scenarios_data.append({
                    'failure_rate_scenario': f"{int(rate * 100)}%",
                    'simulated_payout': payout_value,
                    'associated_profit': total_revenue - payout_value
                })
        df_all_scenarios = pd.DataFrame(all_scenarios_data)

        # 2. Data for Breakeven Analysis
        failure_rate_range = np.arange(0.01, 1.00, 0.01)
        breakeven_results = run_vectorized_simulation(trader_accounts, n_simulations, failure_rate_range, payout_per_successful_account)
        profit_data = [{'failure_rate': rate, 'estimated_profit': total_revenue - np.mean(payouts)} for rate, payouts in breakeven_results.items()]
        df_profit = pd.DataFrame(profit_data).sort_values('failure_rate')

        # 3. Data for Risk Analysis
        if distribution_mode == 'Simulate Average':
            df_risk_analysis = run_risk_analysis(num_traders, n_simulations, scenario_failure_rates, payout_per_successful_account)
        else:
            df_risk_analysis = run_randomized_risk_analysis(num_traders, n_simulations, scenario_failure_rates, payout_per_successful_account)

        # 4. Summary data
        summary_params = {
            "Parameter": ["Distribution Mode", "Number of Traders", "Simulations per Scenario", "Revenue per Account", "Payout per Success", "Additional Revenue/Fixed Costs", "Total Calculated Revenue"],
            "Value": [distribution_mode, f"{num_traders:,}", f"{n_simulations:,}", f"${cost_per_account:,.2f}", f"${payout_per_successful_account:,.2f}", f"${additional_revenue:,.2f}", f"${total_revenue:,.2f}"]
        }
        df_summary = pd.DataFrame(summary_params)


    # <<< NEW: Prepare and offer the main Excel download button >>>
    report_data_dict = {
        "Summary_Parameters": df_summary,
        "Scenario_Analysis_Raw": df_all_scenarios,
        "Breakeven_Analysis": df_profit,
        "Risk_Analysis": df_risk_analysis
    }
    excel_bytes = dfs_to_excel_bytes(report_data_dict)

    st.download_button(
        label="📥 Download Full Report as Excel",
        data=excel_bytes,
        file_name=f"full_capex_report_{distribution_mode.replace(' ', '_').lower()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.markdown("---")


    # --- Display Data in Tabs (No More Calculations Here) ---
    tab1, tab2, tab3 = st.tabs(["Scenario Analysis", "Breakeven Analysis", "Risk Analysis"])

    with tab1:
        st.header("Payout & Profitability Scenarios")
        for rate in scenario_failure_rates:
            payouts = simulation_results[rate]
            mean_payout = np.mean(payouts)
            std_payout = np.std(payouts)
            
            st.subheader(f"Scenario: {int(rate * 100)}% Failure Rate")
            col1, col2, col3 = st.columns(3)
            with col1:
                col1.metric("Average Payout (Outflow)", f"${mean_payout:,.2f}")
                col1.metric("Std. Dev. of Payout (Volatility)", f"${std_payout:,.2f}")
            with col2:
                estimated_net_profit = total_revenue - mean_payout
                col2.metric("Estimated Net Profit", f"${estimated_net_profit:,.2f}")
                profit_minus_1_std = total_revenue - (mean_payout + std_payout)
                profit_plus_1_std = total_revenue - (mean_payout - std_payout)
                col2.write("68% Confidence Profit Range:")
                col2.write(f"`${profit_minus_1_std:,.2f}` to `${profit_plus_1_std:,.2f}`")
            with col3:
                df_chart = pd.DataFrame({'Payouts': payouts})
                chart = create_dist_chart(df_chart, "Distribution of Potential Payouts")
                col3.altair_chart(chart, use_container_width=True)

    with tab2:
        st.header("Find Lowest Profitable Failure Rate")
        df_profitable = df_profit[df_profit['estimated_profit'] > 0]
        if not df_profitable.empty:
            lowest_profitable_rate = df_profitable['failure_rate'].min()
            highest_profit_at_lowest_rate = df_profitable.loc[df_profitable['failure_rate'] == lowest_profitable_rate, 'estimated_profit'].iloc[0]
            st.success(f"The lowest failure rate with a positive estimated profit is **{lowest_profitable_rate * 100:.2f}%**.")
            profit_chart = alt.Chart(df_profit).mark_area(
                line={'color':'darkgreen'},
                color=alt.Gradient(
                    gradient='linear',
                    stops=[alt.GradientStop(color='red', offset=0), alt.GradientStop(color='white', offset=0.5), alt.GradientStop(color='green', offset=1)],
                    x1=1, x2=1, y1=1, y2=0)
            ).encode(
                x=alt.X('failure_rate:Q', axis=alt.Axis(format='%'), title='Failure Rate'),
                y=alt.Y('estimated_profit:Q', title='Estimated Profit ($)')
            ).properties(title="Estimated Profit vs. Failure Rate")
            st.altair_chart(profit_chart, use_container_width=True)
        else:
            st.warning("No profitable failure rate found within the analyzed range.")

    with tab3:
        st.header("Risk Analysis")
        if distribution_mode == 'Simulate Average':
            st.subheader("Volatility vs. Account Concentration")
            st.write("This chart shows how risk... changes as we adjust the **average** number of accounts...")
            if not df_risk_analysis.empty:
                std_dev_chart = alt.Chart(df_risk_analysis).mark_line(point=True).encode(
                    x=alt.X('Average Accounts per Trader:Q', title="Avg. Accounts per Trader"),
                    y=alt.Y('Standard Deviation:Q', title="Standard Deviation of Payouts (Risk)"),
                    color=alt.Color('Failure Rate:N', title="Failure Rate"),
                    tooltip=['Average Accounts per Trader', 'Failure Rate', 'Standard Deviation']
                ).properties(title="Risk vs. Average Account Concentration").interactive()
                st.altair_chart(std_dev_chart, use_container_width=True)
        else: # Randomized mode
            st.subheader("Volatility vs. Account Unpredictability")
            st.write("This chart shows how risk... changes as the **unpredictability** of accounts per trader increases...")
            if not df_risk_analysis.empty:
                random_risk_chart = alt.Chart(df_risk_analysis).mark_line(point=True).encode(
                    x=alt.X('Max Accounts in Range:Q', title="Max Possible Accounts per Trader"),
                    y=alt.Y('Standard Deviation:Q', title="Standard Deviation of Payouts (Risk)"),
                    color=alt.Color('Failure Rate:N', title="Failure Rate"),
                    tooltip=['Max Accounts in Range', 'Failure Rate', 'Standard Deviation']
                ).properties(title="Risk vs. Account Range Width").interactive()
                st.altair_chart(random_risk_chart, use_container_width=True)

# --- APP ROUTING ---
# This must be the first Streamlit command in the script.
st.set_page_config(layout="wide")

if check_login():
    main_app()
