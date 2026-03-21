import warnings
warnings.filterwarnings("ignore")
import os
os.environ["PYTHONWARNINGS"] = "ignore"

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Digital Ledger",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded",
)

from database import create_indexes
from auth import register_user, login_user
from customers import (add_customer, get_customers, get_defaulters,
                       delete_customer, customer_portal_login, update_customer_pin)
from transactions import (add_transaction, edit_transaction,
                           delete_transaction, get_transactions)
from analytics import get_summary_stats, get_monthly_trend_df, get_risk_distribution
from reminders import run_monthly_reminders, start_scheduler
from invoice import generate_invoice
from otp import send_otp_to_phone, reset_password_with_otp
from activity_log import log_action, get_logs, clear_logs
from bulk_import import import_customers_from_excel, generate_template
from receipts import send_receipt

@st.cache_resource
def init_db():
    create_indexes()
    return start_scheduler()

init_db()

def _def(key, val):
    if key not in st.session_state:
        st.session_state[key] = val

_def("logged_in",            False)
_def("user_id",              "")
_def("username",             "")
_def("business_name",        "")
_def("theme",                "dark")
_def("mode",                 "merchant")
_def("cust_logged_in",       False)
_def("cust_data",            {})
_def("otp_phone",            "")
_def("otp_sent",             False)
_def("edit_txn_id",          None)


def inject_theme():
    dark = st.session_state.theme == "dark"
    bg       = "#0f0f1a" if dark else "#f5f7ff"
    card_bg  = "#1a1a2e" if dark else "#ffffff"
    text     = "#e8e8ff" if dark else "#1a1a2e"
    border   = "#2a2a4a" if dark else "#dde0f0"
    sidebar  = "#12122a" if dark else "#1a1a2e"

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stApp {{ background: {bg}; color: {text}; }}
    section[data-testid="stSidebar"] {{ background: {sidebar} !important; }}
    section[data-testid="stSidebar"] * {{ color: #eee !important; }}
    .metric-card {{
        background: linear-gradient(135deg, #667eea, #764ba2);
        padding: 18px; border-radius: 14px; color: white;
        text-align: center; margin-bottom: 12px;
        box-shadow: 0 4px 20px rgba(102,126,234,0.3);
    }}
    .metric-card h3 {{ font-size: 1.9rem; margin: 4px 0 0; }}
    .metric-card p  {{ margin: 0; opacity: 0.85; font-size: 0.85rem; }}
    .info-card {{
        background: {card_bg}; border: 1px solid {border};
        border-radius: 12px; padding: 16px; margin-bottom: 10px;
    }}
    .stButton > button {{ border-radius: 8px !important; transition: all 0.2s; }}
    .stTextInput input, .stNumberInput input {{ border-radius: 8px !important; }}
    </style>
    """, unsafe_allow_html=True)


def show_auth_page():
    inject_theme()
    col1, col2, col3 = st.columns([1, 2.2, 1])
    with col2:
        st.markdown("## 📒 Digital Ledger")
        st.markdown("##### Paperless credit management for small businesses")
        st.divider()

        tabs = st.tabs(["🔑 Merchant Login", "📝 Register", "👤 Customer Portal", "🔓 Forgot Password"])

        with tabs[0]:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Login", use_container_width=True):
                    res = login_user(username, password)
                    if res["success"]:
                        st.session_state.logged_in     = True
                        st.session_state.user_id       = res["user_id"]
                        st.session_state.username      = res["username"]
                        st.session_state.business_name = res["business_name"]
                        st.session_state.mode          = "merchant"
                        log_action(res["user_id"], "LOGIN", f"User {username} logged in")
                        st.rerun()
                    else:
                        st.error(res["message"])

        with tabs[1]:
            with st.form("register_form"):
                c1, c2 = st.columns(2)
                new_user  = c1.text_input("Username")
                biz_name  = c2.text_input("Business Name")
                phone     = st.text_input("Your Phone Number (for OTP recovery)")
                new_pass  = st.text_input("Password", type="password")
                conf_pass = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Register", use_container_width=True):
                    if new_pass != conf_pass:
                        st.error("Passwords do not match.")
                    elif not all([new_user, biz_name, phone, new_pass]):
                        st.error("All fields are required.")
                    else:
                        res = register_user(new_user, new_pass, biz_name, phone)
                        if res["success"]:
                            st.success("Account created! Please login.")
                        else:
                            st.error(res["message"])

        with tabs[2]:
            st.info("Customers: log in with your phone number and PIN set by your merchant.")
            with st.form("cust_login_form"):
                cphone = st.text_input("Your Phone Number")
                cpin   = st.text_input("PIN (4 digits)", type="password", max_chars=4)
                if st.form_submit_button("Customer Login", use_container_width=True):
                    res = customer_portal_login(cphone, cpin)
                    if res["success"]:
                        st.session_state.cust_logged_in = True
                        st.session_state.cust_data      = res["customer"]
                        st.session_state.mode           = "customer"
                        st.rerun()
                    else:
                        st.error(res["message"])

        with tabs[3]:
            if not st.session_state.otp_sent:
                with st.form("otp_request_form"):
                    fp_phone = st.text_input("Registered Phone Number")
                    if st.form_submit_button("Send OTP", use_container_width=True):
                        res = send_otp_to_phone(fp_phone)
                        if res["success"]:
                            st.session_state.otp_phone = fp_phone
                            st.session_state.otp_sent  = True
                            st.success(res["message"])
                            st.rerun()
                        else:
                            st.error(res["message"])
            else:
                st.success(f"OTP sent to {st.session_state.otp_phone}")
                with st.form("otp_verify_form"):
                    otp      = st.text_input("Enter OTP")
                    new_pass = st.text_input("New Password", type="password")
                    conf     = st.text_input("Confirm New Password", type="password")
                    c1, c2   = st.columns(2)
                    if c1.form_submit_button("Reset Password", use_container_width=True):
                        if new_pass != conf:
                            st.error("Passwords don't match.")
                        else:
                            res = reset_password_with_otp(st.session_state.otp_phone, otp, new_pass)
                            if res["success"]:
                                st.success("Password reset! Please login.")
                                st.session_state.otp_sent  = False
                                st.session_state.otp_phone = ""
                            else:
                                st.error(res["message"])
                    if c2.form_submit_button("← Back", use_container_width=True):
                        st.session_state.otp_sent = False
                        st.rerun()


def show_customer_portal():
    inject_theme()
    cust = st.session_state.cust_data
    mid  = cust.get("merchant_id", "")

    with st.sidebar:
        st.markdown("### 👤 Customer Portal")
        st.markdown(f"**{cust.get('name', '')}**")
        st.markdown(f"📞 {cust.get('phone', '')}")
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.cust_logged_in = False
            st.session_state.cust_data      = {}
            st.session_state.mode           = "merchant"
            st.rerun()

    st.header(f"👋 Hello, {cust.get('name', '')}!")

    balance = cust.get("balance", 0)
    color   = "#e74c3c" if balance > 0 else "#27ae60"
    st.markdown(f"""
    <div class="metric-card" style="background: linear-gradient(135deg, {color}, #333);">
        <p>Your Outstanding Balance</p>
        <h3>₹{balance:,.2f}</h3>
        <p>{'Please clear your dues' if balance > 0 else '✅ All clear!'}</p>
    </div>""", unsafe_allow_html=True)

    st.divider()
    st.subheader("📜 Your Transactions")
    txns = get_transactions(mid, cust["_id"])
    if txns:
        df = pd.DataFrame(txns)
        df["date"]   = pd.to_datetime(df["date"]).dt.strftime("%d %b %Y")
        df["type"]   = df["type"].map({"credit": "💸 Credit", "payment": "✅ Payment"})
        df["amount"] = df["amount"].map(lambda x: f"₹{x:,.2f}")
        st.dataframe(df[["date", "type", "amount", "note"]], use_container_width=True, hide_index=True)

        st.divider()
        if st.button("📄 Download My Invoice (PDF)", use_container_width=True):
            raw_txns = get_transactions(mid, cust["_id"])
            for t in raw_txns:
                if not hasattr(t["date"], "strftime"):
                    t["date"] = pd.to_datetime(t["date"])
            from database import get_users_col
            from bson import ObjectId as ObjId
            merchant = get_users_col().find_one({"_id": ObjId(mid)})
            biz = merchant["business_name"] if merchant else "Your Merchant"
            pdf = generate_invoice(biz, cust["name"], cust["phone"], raw_txns, balance)
            st.download_button("⬇️ Download PDF", data=pdf,
                               file_name=f"invoice_{cust['name'].replace(' ','_')}.pdf",
                               mime="application/pdf", use_container_width=True)
    else:
        st.info("No transactions found for your account.")


def show_sidebar():
    inject_theme()
    with st.sidebar:
        st.markdown("### 📒 Digital Ledger")
        st.markdown(f"**{st.session_state.business_name}**")
        st.markdown(f"*@{st.session_state.username}*")
        st.divider()

        page = st.radio("Navigate", [
            "📊 Dashboard",
            "👥 Customers",
            "💳 Transactions",
            "⚠️ Defaulters",
            "🔔 Reminders",
            "📋 Activity Log",
        ])
        st.divider()

        dark_mode = st.toggle("🌙 Dark Mode", value=(st.session_state.theme == "dark"))
        st.session_state.theme = "dark" if dark_mode else "light"

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            log_action(st.session_state.user_id, "LOGOUT", "User logged out")
            for k in ["logged_in", "user_id", "username", "business_name"]:
                st.session_state[k] = False if k == "logged_in" else ""
            st.rerun()
    return page


def show_dashboard():
    st.header("📊 Dashboard")
    mid   = st.session_state.user_id
    stats = get_summary_stats(mid)

    c1, c2, c3, c4 = st.columns(4)
    for col, label, value in [
        (c1, "👥 Customers",       stats["total_customers"]),
        (c2, "⚠️ Defaulters",      stats["defaulters"]),
        (c3, "💰 Total Credit",    f"₹{stats['total_credit']:,.2f}"),
        (c4, "✅ Collection Rate", f"{stats['collection_rate']}%"),
    ]:
        with col:
            st.markdown(f'<div class="metric-card"><p>{label}</p><h3>{value}</h3></div>',
                        unsafe_allow_html=True)

    st.divider()
    cl, cr = st.columns([2, 1])

    with cl:
        st.subheader("📈 Monthly Trends")
        df = get_monthly_trend_df(mid)
        if df.empty:
            st.info("No transactions yet.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df["month"], y=df["credit"],  name="Credit",  marker_color="#e74c3c"))
            fig.add_trace(go.Bar(x=df["month"], y=df["payment"], name="Payment", marker_color="#27ae60"))
            fig.update_layout(barmode="group", height=340,
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    with cr:
        st.subheader("🎯 Risk Distribution")
        rdf = get_risk_distribution(mid)
        if rdf.empty:
            st.info("No customers yet.")
        else:
            colors_map = {"Low Risk": "#27ae60", "Medium Risk": "#f39c12",
                          "High Risk": "#e74c3c", "Defaulter": "#8e44ad"}
            fig2 = px.pie(rdf, names="category", values="count",
                          color="category", color_discrete_map=colors_map, height=340)
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📋 Outstanding Balances")
    customers = get_customers(mid)
    pending = [c for c in customers if c.get("balance", 0) > 0]
    if pending:
        df2 = pd.DataFrame(pending)[["name", "phone", "balance", "risk_category"]]
        df2.columns = ["Customer", "Phone", "Balance (₹)", "Risk"]
        df2 = df2.sort_values("Balance (₹)", ascending=False)
        st.dataframe(df2, use_container_width=True, hide_index=True)
    else:
        st.success("🎉 No outstanding balances!")


def show_customers():
    st.header("👥 Customers")
    mid = st.session_state.user_id

    tab_list, tab_add, tab_bulk = st.tabs(["📋 Customer List", "➕ Add Customer", "📤 Bulk Import"])

    with tab_add:
        with st.form("add_customer_form"):
            c1, c2 = st.columns(2)
            name    = c1.text_input("Customer Name *")
            phone   = c2.text_input("Phone Number *")
            address = st.text_input("Address (optional)")
            pin     = st.text_input("Portal PIN (4-digit, optional)", max_chars=4,
                                    help="Set a PIN so the customer can log into the Customer Portal")
            if st.form_submit_button("Add Customer", use_container_width=True):
                if not name or not phone:
                    st.error("Name and phone are required.")
                elif pin and (not pin.isdigit() or len(pin) != 4):
                    st.error("PIN must be exactly 4 digits.")
                else:
                    res = add_customer(mid, name, phone, address, pin)
                    if res["success"]:
                        log_action(mid, "ADD_CUSTOMER", f"Added {name} ({phone})")
                        st.success(f"Customer '{name}' added!")
                        st.rerun()
                    else:
                        st.error(res["message"])

    with tab_bulk:
        st.markdown("Upload an Excel file with columns: **name**, **phone**, **address** (optional)")
        templ = generate_template()
        st.download_button("⬇️ Download Template", data=templ,
                           file_name="customer_import_template.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        uploaded = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])
        if uploaded:
            if st.button("📤 Import Customers", use_container_width=True):
                with st.spinner("Importing..."):
                    res = import_customers_from_excel(mid, uploaded)
                if res["success"]:
                    r = res["results"]
                    st.success(f"✅ {r['added']} customers added, {r['failed']} failed.")
                    log_action(mid, "BULK_IMPORT", f"{r['added']} customers imported")
                    if r["errors"]:
                        with st.expander("⚠️ Errors"):
                            for e in r["errors"]:
                                st.write(e)
                else:
                    st.error(res["message"])

    with tab_list:
        customers = get_customers(mid)
        if not customers:
            st.info("No customers yet. Add your first customer.")
            return

        search = st.text_input("🔍 Search by name or phone")
        if search:
            customers = [c for c in customers
                         if search.lower() in c["name"].lower() or search in c["phone"]]

        st.markdown(f"**{len(customers)} customer(s)**")
        risk_icon = {"Low Risk": "🟢", "Medium Risk": "🟡", "High Risk": "🔴", "Defaulter": "🟣"}

        for c in customers:
            with st.expander(f"{c['name']}  —  📞 {c['phone']}  —  Balance: ₹{c['balance']:,.2f}"):
                col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
                col1.metric("Balance",      f"₹{c['balance']:,.2f}")
                col2.metric("Total Credit", f"₹{c['total_credit']:,.2f}")
                col3.metric("Total Paid",   f"₹{c['total_paid']:,.2f}")
                col4.metric("Credit Score", c.get("credit_score", 100))

                cat = c.get("risk_category", "Low Risk")
                st.markdown(f"**Risk:** {risk_icon.get(cat,'🟢')} {cat}")
                if c.get("address"):
                    st.markdown(f"**Address:** {c['address']}")

                btn1, btn2, btn3 = st.columns(3)

                with btn1:
                    with st.form(f"pin_form_{c['_id']}"):
                        new_pin = st.text_input("Set Portal PIN", max_chars=4, key=f"pin_{c['_id']}")
                        if st.form_submit_button("Update PIN"):
                            if new_pin and new_pin.isdigit() and len(new_pin) == 4:
                                update_customer_pin(c["_id"], mid, new_pin)
                                log_action(mid, "UPDATE_PIN", f"Updated PIN for {c['name']}")
                                st.success("PIN updated!")
                            else:
                                st.error("PIN must be 4 digits.")

                with btn2:
                    txns = get_transactions(mid, c["_id"])
                    if txns:
                        for t in txns:
                            if not hasattr(t.get("date"), "strftime"):
                                t["date"] = pd.to_datetime(t["date"])
                        pdf = generate_invoice(
                            st.session_state.business_name,
                            c["name"], c["phone"], txns, c["balance"]
                        )
                        st.download_button(
                            "📄 Invoice PDF", data=pdf,
                            file_name=f"invoice_{c['name'].replace(' ','_')}.pdf",
                            mime="application/pdf", key=f"inv_{c['_id']}"
                        )

                with btn3:
                    if st.button("🗑️ Delete Customer", key=f"del_{c['_id']}"):
                        res = delete_customer(c["_id"], mid)
                        if res["success"]:
                            log_action(mid, "DELETE_CUSTOMER", f"Deleted {c['name']}")
                            st.success("Customer deleted.")
                            st.rerun()


def show_transactions():
    st.header("💳 Transactions")
    mid       = st.session_state.user_id
    customers = get_customers(mid)

    if not customers:
        st.info("Add customers first.")
        return

    cust_map = {c["name"]: c for c in customers}

    with st.expander("➕ Record New Transaction", expanded=True):
        with st.form("txn_form"):
            c1, c2, c3 = st.columns(3)
            cust_name = c1.selectbox("Customer", list(cust_map.keys()))
            txn_type  = c2.selectbox("Type", ["credit", "payment"],
                                     format_func=lambda x: "💸 Credit (gave)" if x=="credit" else "✅ Payment (received)")
            amount    = c3.number_input("Amount (₹)", min_value=0.01, step=1.0)
            note      = st.text_input("Note (optional)")
            c4, c5    = st.columns(2)
            send_rcpt = c4.checkbox("📲 Send receipt to customer")
            channel   = c5.selectbox("via", ["whatsapp", "sms"]) if send_rcpt else "whatsapp"

            if st.form_submit_button("Record Transaction", use_container_width=True):
                cust = cust_map[cust_name]
                res  = add_transaction(mid, cust["_id"], txn_type, amount, note)
                if res["success"]:
                    log_action(mid, "ADD_TXN", f"{txn_type.capitalize()} ₹{amount:.2f} for {cust_name}")
                    st.success(f"✅ Recorded ₹{amount:.2f} {txn_type} for {cust_name}")
                    if send_rcpt:
                        rcpt = send_receipt(
                            st.session_state.business_name,
                            cust_name, cust["phone"],
                            txn_type, amount, res["new_balance"], channel
                        )
                        if rcpt.get("success"):
                            st.info(f"📲 Receipt sent via {channel}!")
                        else:
                            st.warning("Receipt send failed — check Twilio config.")
                    st.rerun()
                else:
                    st.error(res["message"])

    st.divider()
    st.subheader("📜 Transaction History")

    filter_cust = st.selectbox("Filter by customer", ["All"] + list(cust_map.keys()))
    cid_filter  = cust_map[filter_cust]["_id"] if filter_cust != "All" else None
    txns        = get_transactions(mid, cid_filter)

    if not txns:
        st.info("No transactions found.")
        return

    for t in txns:
        date_str = pd.to_datetime(t["date"]).strftime("%d %b %Y, %I:%M %p") if t.get("date") else ""
        typ_icon = "💸" if t["type"] == "credit" else "✅"
        edited   = " *(edited)*" if t.get("edited") else ""

        with st.expander(f"{typ_icon} {t['customer_name']} — ₹{t['amount']:,.2f} — {date_str}{edited}"):
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Type:** {t['type'].capitalize()}")
            c2.write(f"**Amount:** ₹{t['amount']:,.2f}")
            c3.write(f"**Note:** {t.get('note','—')}")

            ea, eb = st.columns(2)

            with ea:
                with st.form(f"edit_{t['_id']}"):
                    new_amt  = st.number_input("New Amount", value=float(t["amount"]), min_value=0.01, step=1.0)
                    new_note = st.text_input("New Note", value=t.get("note", ""))
                    if st.form_submit_button("✏️ Save Edit"):
                        res = edit_transaction(t["_id"], mid, new_amt, new_note)
                        if res["success"]:
                            log_action(mid, "EDIT_TXN", f"Edited txn {t['_id']}")
                            st.success("Transaction updated.")
                            st.rerun()
                        else:
                            st.error(res["message"])

            with eb:
                if st.button("🗑️ Delete", key=f"dtxn_{t['_id']}"):
                    res = delete_transaction(t["_id"], mid)
                    if res["success"]:
                        log_action(mid, "DELETE_TXN", f"Deleted txn for {t['customer_name']}")
                        st.success("Transaction deleted.")
                        st.rerun()


def show_defaulters():
    st.header("⚠️ Defaulters")
    mid        = st.session_state.user_id
    defaulters = get_defaulters(mid)

    if not defaulters:
        st.success("🎉 No defaulters! All customers are clear.")
        return

    total = sum(d["balance"] for d in defaulters)
    st.error(f"**{len(defaulters)} customers** owe a total of **₹{total:,.2f}**")

    risk_color = {"Low Risk": "#27ae60", "Medium Risk": "#f39c12",
                  "High Risk": "#e74c3c", "Defaulter": "#8e44ad"}

    for d in sorted(defaulters, key=lambda x: x["balance"], reverse=True):
        cat   = d.get("risk_category", "Low Risk")
        color = risk_color.get(cat, "#27ae60")
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        c1.markdown(f"**{d['name']}**  \n📞 {d['phone']}")
        c2.metric("Outstanding", f"₹{d['balance']:,.2f}")
        c3.metric("Score", d.get("credit_score", 100))
        c4.markdown(f"<span style='color:{color};font-weight:bold'>{cat}</span>",
                    unsafe_allow_html=True)
        st.divider()


def show_reminders():
    st.header("🔔 Payment Reminders")
    mid = st.session_state.user_id

    st.info("⏰ **Auto-reminders** fire on the **1st of every month at 9 AM UTC**. "
            "You can also send them manually below.")

    defaulters = get_defaulters(mid)
    if not defaulters:
        st.success("No outstanding balances — nothing to remind!")
        return

    st.markdown(f"**{len(defaulters)} customers** will receive a reminder:")
    for d in defaulters:
        st.markdown(f"- {d['name']} — 📞 {d['phone']} — ₹{d['balance']:,.2f}")

    st.divider()
    channel = st.radio("Send via", ["whatsapp", "sms"],
                       format_func=lambda x: "💬 WhatsApp" if x=="whatsapp" else "📱 SMS",
                       horizontal=True)

    if st.button("📤 Send Reminders Now", use_container_width=True, type="primary"):
        with st.spinner("Sending..."):
            results = run_monthly_reminders(merchant_id=mid, channel=channel)
        log_action(mid, "SEND_REMINDERS", f"Sent {len(results)} reminders via {channel}")
        df = pd.DataFrame(results)
        df.columns = ["Customer", "Phone", "Balance (₹)", "Status", "Detail"]
        st.dataframe(df, use_container_width=True, hide_index=True)
        sent = sum(1 for r in results if r["status"] == "sent")
        st.success(f"✅ {sent}/{len(results)} reminders sent.")


def show_activity_log():
    st.header("📋 Activity Log")
    mid  = st.session_state.user_id
    logs = get_logs(mid)

    if not logs:
        st.info("No activity recorded yet.")
        return

    c1, c2 = st.columns([4, 1])
    c1.markdown(f"**{len(logs)} recent actions**")
    if c2.button("🗑️ Clear Log"):
        clear_logs(mid)
        log_action(mid, "CLEAR_LOG", "Activity log cleared")
        st.rerun()

    action_icons = {
        "LOGIN": "🔑", "LOGOUT": "🚪",
        "ADD_CUSTOMER": "👤➕", "DELETE_CUSTOMER": "👤🗑️",
        "ADD_TXN": "💳➕", "EDIT_TXN": "✏️", "DELETE_TXN": "💳🗑️",
        "BULK_IMPORT": "📤", "UPDATE_PIN": "🔐",
        "SEND_REMINDERS": "🔔", "CLEAR_LOG": "🗑️",
    }

    df = pd.DataFrame(logs)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%d %b %Y, %I:%M %p")
    df["icon"]      = df["action"].map(lambda a: action_icons.get(a, "📝"))
    df["action"]    = df["icon"] + "  " + df["action"]
    display = df[["timestamp", "action", "details"]].copy()
    display.columns = ["Time", "Action", "Details"]
    st.dataframe(display, use_container_width=True, hide_index=True)


def main():
    if st.session_state.mode == "customer" and st.session_state.cust_logged_in:
        show_customer_portal()
        return

    if not st.session_state.logged_in:
        show_auth_page()
        return

    page = show_sidebar()
    if   page == "📊 Dashboard":    show_dashboard()
    elif page == "👥 Customers":    show_customers()
    elif page == "💳 Transactions": show_transactions()
    elif page == "⚠️ Defaulters":  show_defaulters()
    elif page == "🔔 Reminders":    show_reminders()
    elif page == "📋 Activity Log": show_activity_log()


if __name__ == "__main__":
    main()
