import streamlit as st
from bot import run_bot

st.title("🚀 Pi Super Bot (Mainnet)")

wallet_phrase = st.text_input("Enter your Wallet Phrase", type="password")
to_address = st.text_input("Enter Destination Wallet Address")
runtime = st.number_input("Bot Runtime (seconds)", min_value=10, max_value=600, value=60)

log_area = st.empty()    # Live log area
locked_area = st.empty() # Show total locked balance

if st.button("Start Bot"):
    if not wallet_phrase or not to_address:
        st.error("Please enter Wallet Phrase and Destination Address")
    else:
        st.info("Bot started! Logs will appear below.")
        total_locked = run_bot(wallet_phrase, to_address, runtime, log_area)
        if total_locked is not None:
            locked_area.success(f"Total Locked Balance: {total_locked} PI")
        else:
            locked_area.error("❌ Failed to fetch locked balance or login failed")
