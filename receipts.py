from reminders import send_sms, send_whatsapp


def send_receipt(business_name: str, customer_name: str, customer_phone: str,
                 txn_type: str, amount: float, new_balance: float,
                 channel: str = "whatsapp") -> dict:
    """Send a transaction receipt to customer via SMS or WhatsApp."""

    if txn_type == "credit":
        action = f"a credit of ₹{amount:,.2f} has been recorded against your account"
    else:
        action = f"a payment of ₹{amount:,.2f} has been received — thank you!"

    balance_line = (
        f"Outstanding balance: ₹{new_balance:,.2f}"
        if new_balance > 0
        else "Your account is fully settled. ✅"
    )

    message = (
        f"Dear {customer_name},\n\n"
        f"From {business_name}: {action}.\n"
        f"{balance_line}\n\n"
        f"For queries, contact your merchant."
    )

    if channel == "whatsapp":
        return send_whatsapp(customer_phone, message)
    return send_sms(customer_phone, message)
