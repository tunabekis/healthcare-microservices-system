"""Frontend (Client Layer).

Streamlit dashboard that acts as the single entry point for patients:
registration/login, appointment booking, medical history, and bill
payment. It talks to the three backend microservices over HTTP and
holds no business logic or data of its own.
"""

import streamlit as st
import requests
from datetime import date
import pandas as pd

PATIENT_URL = "http://127.0.0.1:8001"
APPT_URL = "http://127.0.0.1:8002"
BILLING_URL = "http://127.0.0.1:8003"
REQUEST_TIMEOUT_SECONDS = 10

st.set_page_config(page_title="Healthcare System", layout="centered")

# --- Session Management ---
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
if "user_name" not in st.session_state:
    st.session_state["user_name"] = None
if "show_pending" not in st.session_state:
    st.session_state["show_pending"] = False
if "show_paid" not in st.session_state:
    st.session_state["show_paid"] = False


# --- Helper Functions ---
def fetch_json(url: str):
    """GET a URL and return its parsed JSON, or None on failure (shows a st.error)."""
    try:
        res = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        if res.status_code == 200:
            return res.json()
        st.error(f"Error: {res.status_code}")
    except requests.exceptions.RequestException as e:
        st.error(f"Service unreachable: {str(e)}")
    return None


def login_user(name, password):
    try:
        res = requests.post(
            f"{PATIENT_URL}/login",
            json={"name": name, "password": password},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if res.status_code == 200:
            data = res.json()
            st.session_state["user_id"] = data["id"]
            st.session_state["user_name"] = data["name"]
            st.rerun()
        else:
            st.error("Login Failed: Incorrect name or password.")
    except requests.exceptions.RequestException as e:
        st.error(f"Patient Service is unreachable: {str(e)}")


def register_user(name, age, password):
    try:
        res = requests.post(
            f"{PATIENT_URL}/register",
            json={"name": name, "age": age, "password": password},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if res.status_code == 200:
            st.success("Registration Successful! Please Log in.")
        else:
            st.error(f"Registration failed: {res.json().get('detail', 'Unknown error')}")
    except requests.exceptions.RequestException as e:
        st.error(f"Patient Service is unreachable: {str(e)}")


def logout():
    st.session_state["user_id"] = None
    st.session_state["user_name"] = None
    st.rerun()


# --- Main App Interface ---

if st.session_state["user_id"] is None:
    # 1. NOT LOGGED IN
    st.title("🏥 Welcome to the Healthcare System")
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        l_name = st.text_input("Name", key="l_name")
        l_pass = st.text_input("Password", type="password", key="l_pass")
        if st.button("Log In"):
            login_user(l_name, l_pass)

    with tab2:
        st.write("New here? Create an account.")
        r_name = st.text_input("Name", key="r_name")
        r_age = st.number_input("Age", min_value=0, step=1)
        r_pass = st.text_input("Password", type="password", key="r_pass")
        if st.button("Register"):
            register_user(r_name, r_age, r_pass)

else:
    # 2. LOGGED IN DASHBOARD
    st.sidebar.write(f"Logged in as: **{st.session_state['user_name']}**")
    if st.sidebar.button("Logout"):
        logout()

    st.title("My Patient Dashboard")

    tab_book, tab_hist, tab_bill = st.tabs(
        ["📅 Book Appointment", "📂 Medical History", "💳 My Bills"]
    )

    # --- BOOKING TAB ---
    with tab_book:
        st.header("New Appointment")
        with st.form("booking_form"):
            col1, col2 = st.columns(2)
            doctor = col1.selectbox(
                "Select Doctor",
                ["Dr. Gregory House", "Dr. Meredith Grey", "Dr. Shaun Murphy"],
            )
            appt_date = col2.date_input("Select Date", min_value=date.today())

            # Constraint: Specific Time Slots
            time_slot = st.selectbox(
                "Select Time", ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"]
            )

            submit = st.form_submit_button("Book Appointment")

            if submit:
                payload = {
                    "patient_id": st.session_state["user_id"],
                    "doctor": doctor,
                    "date": str(appt_date),
                    "time_slot": time_slot,
                }
                try:
                    res = requests.post(
                        f"{APPT_URL}/appointments/", json=payload, timeout=REQUEST_TIMEOUT_SECONDS
                    )
                    if res.status_code == 200:
                        st.success(f"✅ Booked with {doctor} at {time_slot}")
                        st.info("💡 A bill has been automatically generated for this appointment.")
                    else:
                        st.error(f"❌ Failed: {res.json()['detail']}")
                except requests.exceptions.RequestException:
                    st.error("Appointment Service is offline.")

    # --- HISTORY TAB ---
    with tab_hist:
        st.header("My Appointments")

        # Past Appointments
        st.subheader("📋 Past Appointments")
        if st.button("Refresh Past Appointments", key="btn_past"):
            with st.spinner("Loading past appointments..."):
                url = f"{APPT_URL}/appointments/past/{st.session_state['user_id']}"
                st.session_state["past_data"] = fetch_json(url)

        if st.session_state.get("past_data") is not None:
            if st.session_state["past_data"]:
                df = pd.DataFrame(st.session_state["past_data"])
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No past appointments found.")

        st.divider()

        # Upcoming Appointments
        st.subheader("📅 Upcoming Appointments")
        if st.button("Refresh Upcoming Appointments", key="btn_upcoming"):
            with st.spinner("Loading upcoming appointments..."):
                url = f"{APPT_URL}/appointments/upcoming/{st.session_state['user_id']}"
                st.session_state["upcoming_data"] = fetch_json(url)

        if st.session_state.get("upcoming_data") is not None:
            if st.session_state["upcoming_data"]:
                df = pd.DataFrame(st.session_state["upcoming_data"])
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No upcoming appointments found.")

    # --- BILLS TAB ---
    with tab_bill:
        st.header("My Invoices")

        col1, col2 = st.columns(2)

        # Pending Bills
        with col1:
            st.subheader("⏳ Pending Bills (Unpaid)")
            if st.button("Refresh Pending Bills"):
                st.session_state["show_pending"] = True

            if st.session_state.get("show_pending", False):
                with st.spinner("Loading pending bills..."):
                    url = f"{BILLING_URL}/bills/pending/{st.session_state['user_id']}"
                    data = fetch_json(url)
                    if data:
                        for bill in data:
                            col_a, col_b, col_c = st.columns([2, 1, 1])
                            col_a.write(f"**Amount:** ${bill['amount']}")
                            col_b.write(f"**Date:** {bill['date']}")
                            if col_c.button("💳 Pay", key=f"pay_{bill['id']}"):
                                try:
                                    pay_res = requests.post(
                                        f"{BILLING_URL}/bills/pay",
                                        json={"bill_id": bill["id"]},
                                        timeout=REQUEST_TIMEOUT_SECONDS,
                                    )
                                    if pay_res.status_code == 200:
                                        st.success("✅ Bill paid successfully!")
                                        st.session_state["show_pending"] = True
                                        st.session_state["show_paid"] = True
                                        st.rerun()
                                    else:
                                        st.error("Payment failed")
                                except requests.exceptions.RequestException as e:
                                    st.error(f"Payment error: {str(e)}")
                    elif data is not None:
                        st.info("No pending bills.")

        # Paid Bills
        with col2:
            st.subheader("✅ Paid Bills")
            if st.button("Refresh Paid Bills"):
                st.session_state["show_paid"] = True

            if st.session_state.get("show_paid", False):
                with st.spinner("Loading paid bills..."):
                    url = f"{BILLING_URL}/bills/paid/{st.session_state['user_id']}"
                    data = fetch_json(url)
                    if data:
                        for bill in data:
                            st.write(f"💰 **${bill['amount']}** - Paid on {bill['date']}")
                    elif data is not None:
                        st.info("No paid bills.")
