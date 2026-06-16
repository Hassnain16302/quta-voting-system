import os
import requests
from flask import current_app

def send_otp_email(recipient_email, otp_code):
    """
    Bypasses SMTP blocks by sending emails via HTTP REST API.
    """
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("MAIL_USERNAME")  # Reuses your existing Gmail address
    
    if not api_key:
        current_app.logger.error("BREVO_API_KEY is missing from environment!")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    payload = {
        "sender": {"name": "Quta Voting System", "email": sender_email},
        "to": [{"email": recipient_email}],
        "subject": "Your Secure Voting OTP",
        "htmlContent": f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; text-align: center; border: 1px solid #e2e8f0; border-radius: 10px;">
            <h2 style="color: #0f172a;">Quta Voting Authentication</h2>
            <p style="color: #475569;">Your one-time verification code is:</p>
            <h1 style="color: #2563eb; letter-spacing: 4px; padding: 10px; background: #f1f5f9; border-radius: 5px;">{otp_code}</h1>
            <p style="color: #64748b; font-size: 12px;">This code will expire shortly. Do not share it.</p>
        </div>
        """
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status() 
        print(f"✅ OTP sent successfully to {recipient_email} via Brevo API")
        return True
    except Exception as e:
        current_app.logger.error(f"API Email Failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
             current_app.logger.error(f"Brevo Error Details: {e.response.text}")
        return False