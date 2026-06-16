from datetime import datetime, timedelta
import random
import string
import os
from app import db, login_manager, mail
from flask_login import UserMixin
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from pytz import timezone
import requests


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # role = db.Column(db.String(50))
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    cnic = db.Column(db.String(13), unique=True, nullable=True)
    # ✅ Add below:
    credentials_password = db.Column(db.String(128), nullable=True)
    credentials_sent = db.Column(db.Boolean, default=False)


    is_candidate = db.Column(db.Boolean, default=False)
    designation = db.Column(db.String(30), nullable=True)
    referral_email = db.Column(db.String(120), nullable=True)
    secondary_email = db.Column(db.String(120), nullable=True)

    is_eligible_voter = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)


    otp_token = db.Column(db.String(100), nullable=True)
    otp_expiration = db.Column(db.DateTime, nullable=True)

    votes = db.relationship("Vote", backref="voter", lazy="dynamic")

    def set_password(self, password_plain):
        self.password_hash = generate_password_hash(password_plain)

    def check_password(self, password_plain):
        return check_password_hash(self.password_hash, password_plain)

    def generate_otp(self, otp_expiration_seconds=60):
        """Generate a 6-digit OTP and set expiration."""
        token = "".join(random.choices(string.digits, k=6))
        self.otp_token = token
        self.otp_expiration = datetime.utcnow() + timedelta(seconds=otp_expiration_seconds)
        db.session.commit()
        return token

    def verify_otp(self, token_input):
        """Check if OTP is correct and still valid."""
        if self.otp_token == token_input and datetime.utcnow() < self.otp_expiration:
            self.otp_token = None
            self.otp_expiration = None
            db.session.commit()
            return True
        return False


    def send_credentials_email(self):
     if not self.credentials_password:
         plain_password = os.urandom(6).hex()
         self.set_password(plain_password)
         self.credentials_password = plain_password
     else:
         plain_password = self.credentials_password

     api_key = os.getenv("BREVO_API_KEY")
     sender_email = os.getenv("MAIL_USERNAME")

     url = "https://api.brevo.com/v3/smtp/email"
     headers = {
         "accept": "application/json",
         "api-key": api_key,
         "content-type": "application/json"
     }

     payload = {
         "sender": {"name": "Quta Voting Admin", "email": sender_email},
         "to": [{"email": self.email}],
         "subject": "Your Voting System Credentials",
         "htmlContent": f"""
         <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
             <h2 style="color: #0f172a;">Welcome to Quta Voting System</h2>
             <p style="color: #475569;">An administrator has registered you to participate in upcoming elections.</p>
             <div style="background: #f1f5f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                 <p style="margin: 5px 0;"><strong>Email:</strong> {self.email}</p>
                 <p style="margin: 5px 0;"><strong>Password:</strong> <span style="color: #ef4444; font-weight: bold;">{plain_password}</span></p>
             </div>
             <p style="color: #64748b; font-size: 12px;">Please log in securely to cast your vote when an election begins.</p>
         </div>
         """
     }

     try:
         response = requests.post(url, json=payload, headers=headers)
         response.raise_for_status()

         self.credentials_sent = True
         db.session.commit()
         print(f"✅ Credentials sent successfully to {self.email} via Brevo API")

     except Exception as e:
         print(f"Brevo API Error (Credentials): {e}")
         if hasattr(e, 'response') and e.response is not None:
              print(f"Brevo Error Details: {e.response.text}")
         raise e

        

class Candidate(db.Model):
    __tablename__ = "candidates"
    __table_args__ = (
    db.UniqueConstraint('user_id', 'election_id', 'designation', name='unique_candidate_per_election'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    designation = db.Column(db.String(30), nullable=False)
    election_id = db.Column(db.Integer, db.ForeignKey("elections.id"), nullable=True)
    contract_cid = db.Column(db.Integer, nullable=True)
    user = db.relationship("User", backref="candidacies")
    election = db.relationship("Election", backref="candidates")

class Election(db.Model):
    __tablename__ = "elections"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    contract_address = db.Column(db.String(100), nullable=True)
    is_closed = db.Column(db.Boolean, default=False)
    total_voters = db.Column(db.Integer, default=0)
    votes_cast = db.Column(db.Integer, default=0)
    

    def check_active(self):
        from app.models import ElectionStatisticsArchive

        now = datetime.utcnow()
        if self.start_time <= now < self.end_time and not self.is_closed:
            self.is_active = True
        else:
            self.is_active = False
            if now >= self.end_time and not self.is_closed:
                self.is_closed = True
                db.session.commit()
                print(f"📢 Election {self.id} closed.")

            # Optional: Safety check to confirm archive exists
            elif self.is_closed:
                archived = ElectionStatisticsArchive.query.filter_by(election_id=self.id).count()
                if archived == 0:
                    print(f"⚠️ Election {self.id} is closed but not archived yet.")

        db.session.commit()
        return self.is_active



    
    def start_time_pkt(self):
        return self.start_datetime.astimezone(timezone("Asia/Karachi"))

    def end_time_pkt(self):
        return self.end_datetime.astimezone(timezone("Asia/Karachi"))


class Vote(db.Model):
    __tablename__ = "votes"
    id = db.Column(db.Integer, primary_key=True)
    voter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidates.id"), nullable=False)
    election_id = db.Column(db.Integer, db.ForeignKey("elections.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    candidate = db.relationship("Candidate", backref="votes_cast")
    election = db.relationship("Election", backref="votes")

    __table_args__ = (
        db.UniqueConstraint("voter_id", "candidate_id", "election_id", name="uix_voter_candidate_election"),
    )


class ElectionStatisticsArchive(db.Model):
    __tablename__ = "election_statistics_archive"
    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer)
    candidate_name = db.Column(db.String(120))
    candidate_email = db.Column(db.String(120))
    designation = db.Column(db.String(100))
    vote_count = db.Column(db.Integer)
    title = db.Column(db.String(150), nullable=False)
    votes_cast = db.Column(db.Integer, default=0)
    total_voters = db.Column(db.Integer, default=0)

class OTPVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), nullable=False)
    otp = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_verified = db.Column(db.Boolean, default=False)

# In voting_system/app/models.py

class Announcement(db.Model):
    __tablename__ = "announcements"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Announcement {self.title}>'