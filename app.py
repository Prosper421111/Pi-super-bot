import streamlit as st
from bot import run_bot

st.title("🚀 PI Super Bot")

# Input fields
phrase = st.text_input("Enter your Wallet Phrase", type="password")
address = st.text_input("Enter Destination Wallet Address")
trials = st.number_input("Number of Trials", min_value=1, max_value=100, value=10)
machine_gun = st.checkbox("Machine Gun Mode (Super Fast)", value=True)
test_mode = st.checkbox("Test Mode (Safe Simulation)", value=True)

# Run button
if st.button("Start Bot"):
    if not phrase or not address:
        st.error("Please enter both Wallet Phrase and Destination Address.")
    else:
        st.success("Bot started! Logs will appear in the console.")
        run_bot(phrase, address, trials, machine_gun, test_mode)
