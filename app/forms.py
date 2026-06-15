from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    BooleanField,
    SelectField,
    DateTimeField,
    HiddenField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import User
from flask import current_app
import re
from flask_wtf.file import FileField, FileRequired, FileAllowed

from wtforms.fields import StringField, DateTimeLocalField, SubmitField



class EligibilityForm(FlaskForm):
    full_name = StringField(
        "Full Name", validators=[DataRequired(), Length(min=2, max=120)]
    )
    designation = SelectField(
        "Select Designation",
        choices=[
            ("Voter", "Voter"),
            ("President", "President"),
            ("Vice President", "Vice President"),
            ("General Secretary", "General Secretary"),
            ("Joint Secretary", "Joint Secretary"),
            ("Finance Secretary", "Finance Secretary"),
            ("Social Secretary", "Social Secretary"),
        ],
        validators=[DataRequired()],
    )
    referral_email = StringField("Referral Email", validators=[Length(max=120)])
    secondary_email = StringField("Secondary Email", validators=[Length(max=120)])
    phone = StringField(
        "Phone Number", validators=[DataRequired(), Length(min=10, max=20)]
    )
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField("Submit")
    
    def validate_referral_email(self, referral_email):
        if self.designation.data != "Voter" and not referral_email.data:
            raise ValidationError("Referral Email is required for candidates.")
        elif referral_email.data and not re.match(r"[^@]+@[^@]+\.[^@]+", referral_email.data):
            raise ValidationError("Invalid email format.")

    def validate_secondary_email(self, secondary_email):
        if self.designation.data != "Voter" and not secondary_email.data:
            raise ValidationError("Secondary Email is required for candidates.")
        elif secondary_email.data and not re.match(r"[^@]+@[^@]+\.[^@]+", secondary_email.data):
            raise ValidationError("Invalid email format.")


    def validate_email(self, email):
        existing = User.query.filter_by(email=email.data).first()
        if existing:
            raise ValidationError("Email already registered.")

    def validate_phone(self, phone):
        # Basic phone number validation (digits only; you can expand)
        if not re.fullmatch(r"\+?\d{10,20}", phone.data):
            raise ValidationError("Enter a valid phone number.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    submit = SubmitField("Login")


class CandidateApprovalForm(FlaskForm):
    user_id = HiddenField("User ID", validators=[DataRequired()])
    designation = HiddenField("Designation", validators=[DataRequired()])
    approve = SubmitField("Approve as Candidate")


class AddCandidateForm(FlaskForm):
    user_id = SelectField("Select Approved Candidate", coerce=int, validators=[DataRequired()])
    designation = SelectField(
        "Designation",
        choices=[
            ("President", "President"),
            ("Vice President", "Vice President"),
            ("General Secretary", "General Secretary"),
            ("Joint Secretary", "Joint Secretary"),
            ("Finance Secretary", "Finance Secretary"),
            ("Social Secretary", "Social Secretary"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Add Candidate")


class AddVoterForm(FlaskForm):
    user_id = SelectField("Select User to Make Eligible Voter", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Add Voter")


class AssignElectionForm(FlaskForm):
    title = StringField("Election Title", validators=[DataRequired()])
    start_datetime = DateTimeLocalField("Start Date & Time (PKT)", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    end_datetime = DateTimeLocalField("End Date & Time (PKT)", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    submit = SubmitField("Assign Election")

    def validate_end_datetime(self, end_datetime):
        if self.start_datetime.data >= end_datetime.data:
            raise ValidationError("End time must be after start time.")


from wtforms import SelectMultipleField
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms.validators import Optional


class SendCredentialsForm(FlaskForm):
    user_id = SelectField("Select Eligible User", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Send Credentials")


class OTPForm(FlaskForm):
    otp = StringField("Enter OTP", validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField("Verify OTP")


class VoteForm(FlaskForm):
    # We’ll dynamically generate one SelectField per designation in the route
    class Meta:
        csrf = True  # or False if you're disabling it
    submit = SubmitField("Submit Votes")

class OTPForm(FlaskForm):
    otp = StringField("Enter OTP", validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField("Verify")
    


class AnnouncementForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(min=5, max=150)])
    content = TextAreaField("Content", validators=[DataRequired(), Length(min=10)])
    submit = SubmitField("Post Announcement")
    
    
class CSVUploadForm(FlaskForm):
    csv_file = FileField(
        "Upload CSV File",
        validators=[
            FileRequired(),
            FileAllowed(["csv"], "Only .csv files are allowed!")
        ]
    )
    submit = SubmitField("Upload and Process")



# ... (at the end of the file)
class AssignDesignationForm(FlaskForm):
    designation = SelectField(
        "Select Designation",
        choices=[
            ("President", "President"),
            ("Vice President", "Vice President"),
            ("General Secretary", "General Secretary"),
            ("Joint Secretary", "Joint Secretary"),
            ("Finance Secretary", "Finance Secretary"),
            ("Social Secretary", "Social Secretary"),
        ],
        validators=[DataRequired()],
    )
    submit_assign = SubmitField("Assign Selected Users")