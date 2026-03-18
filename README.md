# 📒 Digital Ledger — MVP (Full Edition)

A paperless credit management system for small business owners.

## Features
- 🔐 Merchant register/login with bcrypt hashing
- 🔓 Forgot password via OTP (SMS)
- 👥 Customer management with credit scoring
- 💳 Credit & payment transactions (edit/delete with audit trail)
- 📤 Bulk customer import via Excel
- 📄 PDF invoice generation per customer
- 📲 Transaction receipts via SMS/WhatsApp
- ⚠️ Defaulter detection
- 🎯 Rule-based credit scoring (Low/Medium/High Risk/Defaulter)
- 📊 Analytics dashboard
- 🔔 Automated monthly reminders (APScheduler)
- 👤 Customer self-service portal (view balance + download invoice)
- 📋 Activity/audit log
- 🌙 Dark/Light mode toggle

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure .env
```bash
cp .env.example .env
# Fill in MONGO_URI and optionally Twilio credentials
```

### 3. Run
```bash
streamlit run app.py
```

---

## Deploy to Streamlit Cloud (Free)
1. Push this folder to a GitHub repository
2. Go to share.streamlit.io
3. Connect your GitHub repo
4. Set main file: `app.py`
5. Add your .env variables in the Secrets section
6. Click Deploy!

---

## Project Structure
```
ledger_app/
├── app.py            # Main Streamlit UI (all pages)
├── auth.py           # Merchant register/login
├── customers.py      # Customer management + portal login + credit score
├── transactions.py   # Add/edit/delete transactions
├── analytics.py      # Dashboard data
├── reminders.py      # Twilio SMS/WhatsApp + APScheduler
├── invoice.py        # PDF invoice generator (ReportLab)
├── otp.py            # Forgot password OTP
├── activity_log.py   # Audit trail
├── bulk_import.py    # Excel bulk import
├── receipts.py       # Transaction receipts
├── database.py       # MongoDB connection
├── runtime.txt       # Python version for Streamlit Cloud
├── requirements.txt
└── .env.example
```

## Credit Score Rules
| Score  | Category    |
|--------|-------------|
| 75-100 | 🟢 Low Risk  |
| 50-74  | 🟡 Medium Risk |
| 25-49  | 🔴 High Risk |
| 0-24   | 🟣 Defaulter |
