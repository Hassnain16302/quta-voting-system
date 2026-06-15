# app/utils/sms.py
from flask_mail import Message
from flask import current_app
from app import mail

def send_otp_email(recipient_email, otp_code):
    """
    Sends a 6-digit OTP to the voter's registered email address.
    """
    try:
        msg = Message(
            subject="Your QUTA Vote Verification Code",
            recipients=[recipient_email]
        )
        
        msg.body = f"""Hello,

Your One-Time Password (OTP) for secure voting access is: {otp_code}

This code will expire in 5 minutes. Please enter this code in the portal to proceed. 

Best regards,
QUTA Voting System Admin
"""
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email OTP: {e}")
        return False