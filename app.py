import streamlit as st
from bot import run_bot

st.title("🚀 PI Super Bot (Fast & Live)")

wallet_phrase = st.text_input("Enter Wallet Phrase", type="password")
sender_secret = st.text_input("Enter Wallet Secret Key", type="password")
receiver_address = st.text_input("Enter Destination Wallet Address")
trials = st.number_input("Bot Runtime (in cycles)", min_value=1, max_value=100, value=10)

log_area = st.empty()       # live log area
locked_area = st.empty()    # total locked balance

if st.button("Start Bot"):
    if not wallet_phrase or not sender_secret or not receiver_address:
        st.error("Please enter Wallet Phrase, Secret Key, and Destination Address")
    else:
        st.info("Bot started! Logs will appear below.")
        total_locked = run_bot(wallet_phrase, sender_secret, receiver_address, trials, log_area)
        if total_locked is not None:
            locked_area.success(f"Total Locked Balance: {total_locked} PI")
        else:
            locked_area.error("Failed to fetch locked balance")
