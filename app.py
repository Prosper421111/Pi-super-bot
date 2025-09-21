import streamlit as st

import threading

from bot import run_bot



st.title("🚀 PI Bot Web Interface")



phrase = st.text_area("Wallet Phrase", type="password")

address = st.text_input("Receiver Wallet Address")

trials = st.number_input("Trials", min_value=1, max_value=100, value=10)

machine_gun = st.checkbox("Machine Gun Mode", value=True)

test_mode = st.checkbox("Test Mode", value=True)



if st.button("Start Bot"):

    st.success("Bot started! Logs will appear in the console.")

    threading.Thread(

        target=run_bot,

        args=(phrase, address, trials, machine_gun, test_mode)

    ).start()
