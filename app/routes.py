
from flask import current_app
from flask import Blueprint

from app.utils.helpers import patch_candidates_to_latest_election
bp = Blueprint("routes", __name__)

from io import BytesIO
from flask import (
    Response,
    render_template,
    redirect,
    send_file,
    url_for,
    flash,
    request,
    session,
    abort,
    current_app,
)
from app.forms import  SendCredentialsForm, VoteForm, AnnouncementForm, AssignDesignationForm
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
import os
from datetime import datetime
import pytz
from pytz import timezone, utc
import pytz
from datetime import datetime
from app.models import Election, ElectionStatisticsArchive, Vote, Announcement

# In voting_system/app/routes.py
import csv
import io
from app.forms import CSVUploadForm


from app import db
from app.models import User, Candidate, Election, Vote
from app.forms import (
    LoginForm,
    OTPForm,
    AddCandidateForm,
    AddVoterForm,
    AssignElectionForm,
)
from app.blockchain import deploy_contract, load_contract_instance, cast_vote, get_all_votes
import json
from app.blockchain import compile_contract  # ✅ Import this if missing
from flask_wtf.csrf import generate_csrf
from flask import session



def localtime_filter(value, format="%d-%b-%Y %I:%M %p"):
    if value is None:
        return ""
    from pytz import timezone, utc
    utc_zone = utc
    pkt_zone = timezone("Asia/Karachi")

    if value.tzinfo is None:
        value = utc_zone.localize(value)

    return value.astimezone(pkt_zone).strftime(format)

# Registering with the Jinja environment manually
def register_filters(app):
    app.jinja_env.filters["localtime"] = localtime_filter







    # Optional: store voter & turnout data per designation (next step uses this)




from sqlalchemy.exc import IntegrityError
# ... [other imports, assuming User model is imported] ...
from app.models import User # Ensure this is imported

# In voting_system/app/routes.py

# Add this import at the top with the other imports from collections
from collections import defaultdict

# ... other imports ...

@bp.route("/", methods=["GET"])
def index():
    # 1. Fetch Announcements from the database (showing the 3 most recent)
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(3).all()

    # 2. Fetch Voter List (all approved, non-admin users)
    voters = User.query.filter(
        User.is_eligible_voter == True,
        User.email != "admin@university.com"
    ).order_by(User.full_name).all()
    
    # [cite_start]3. Fetch Candidate List, grouped by designation [cite: 988-992]
    all_candidates = Candidate.query.join(User).order_by(User.full_name).all()
    # Define the desired order for designations
    designation_order = [
        "President", "Vice President", "General Secretary",
        "Joint Secretary", "Finance Secretary", "Social Secretary"
    ]
    ordered_candidates = {desig: [] for desig in designation_order}
    for c in all_candidates:
        if c.designation in ordered_candidates:
            ordered_candidates[c.designation].append(c.user)
            
    # Create a preview version (e.g., first 2 per designation)
    candidates_preview = {
        desig: users[:2] for desig, users in ordered_candidates.items() if users
    }
    total_candidates = sum(len(users) for users in ordered_candidates.values())
    total_preview_candidates = sum(len(users) for users in candidates_preview.values())
    grouped_candidates = defaultdict(list)
    for c in all_candidates:
        grouped_candidates[c.designation].append(c.user)

    # 4. Fetch Results from the latest closed election
    latest_election = Election.query.order_by(Election.id.desc()).first()
    archived_results = None
    show_latest_stats_button = False
    # [cite_start]Check if the latest election is closed and has archived data [cite: 1492-1500]
    if latest_election:
       latest_election.check_active() # Ensure status is current
       if latest_election.is_closed:
           archived_entries = ElectionStatisticsArchive.query.filter_by(election_id=latest_election.id).all()
           if archived_entries:
               archived_results = {
                   "election_title": latest_election.title,
                   "data": defaultdict(list)
               }
               for entry in archived_entries:
                   archived_results["data"][entry.designation].append({'name': entry.candidate_name, 'votes': entry.vote_count})
               for designation in archived_results["data"]:
                   archived_results["data"][designation].sort(key=lambda x: x['votes'], reverse=True)
               
               show_latest_stats_button = True # ✅ Set flag if archived


    return render_template(
        "index.html",
        announcements=announcements,
        voters=voters,
        ordered_candidates=ordered_candidates,
        candidates_preview=candidates_preview,
        grouped_candidates=grouped_candidates,
        archived_results=archived_results,
        latest_election=latest_election,
        total_candidates=total_candidates,
        total_preview_candidates=total_preview_candidates,
        show_latest_stats_button=show_latest_stats_button
        )


# -----------------------------------------
# 2. LOGIN (ADMIN & VOTER)
# -----------------------------------------
# Add this import near the top of app/routes.py
from app.utils.email_otp import send_otp_email
@bp.route("/login", methods=["GET", "POST"])
def login(): 
    if current_user.is_authenticated:
        return redirect(url_for("routes.dashboard"))
        
    # Clear any pending 2FA attempts if they return to the login screen
    session.pop("pending_voter_id", None)
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and user.check_password(form.password.data):
            
            # --- ADMIN LOGIN ---
            if user.email.lower() == "admin@university.com":
                login_user(user)     
                session["is_admin"] = True
                return redirect(url_for("routes.admin_panel"))
                
            # --- VOTER LOGIN ---
            if user.is_eligible_voter:
                # ❌ DO NOT call login_user(user) yet!
                # ✅ Temporarily store their ID in the session
                session["pending_voter_id"] = user.id
                session["is_admin"] = False
                
                # Generate and Send OTP
                token = user.generate_otp(otp_expiration_seconds=300) 
                email_sent = send_otp_email(user.email, token)
                
                if email_sent:
                    flash("A verification code has been sent to your registered email.", "info")
                else:
                    flash("System error: Failed to send OTP email. Please try again or contact admin.", "danger")
                    
                return redirect(url_for("routes.verify_otp"))
            else:
                flash("Your account is not yet approved for voting. Please wait for admin approval.", "danger")
        else:
            flash("Incorrect email or password.", "danger")
            
    return render_template("login.html", form=form)


# In voting_system/app/routes.py (Admin section)

@bp.route("/admin/manage_announcements", methods=["GET", "POST"])
@login_required
def manage_announcements():
    if not session.get("is_admin"):
        abort(403)

    form = AnnouncementForm()
    if form.validate_on_submit():
        new_announcement = Announcement(
            title=form.title.data,
            content=form.content.data
        )
        db.session.add(new_announcement)
        db.session.commit()
        flash("Announcement posted successfully.", "success")
        return redirect(url_for("routes.manage_announcements"))

    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template("manage_announcements.html", form=form, announcements=announcements)


@bp.route("/admin/delete_announcement/<int:announcement_id>", methods=["POST"])
@login_required
def delete_announcement(announcement_id):
    if not session.get("is_admin"):
        abort(403)

    announcement = Announcement.query.get_or_404(announcement_id)
    db.session.delete(announcement)
    db.session.commit()
    flash("Announcement deleted successfully.", "info")
    return redirect(url_for("routes.manage_announcements"))

# -----------------------------------------
# 3. OTP VERIFICATION
# -----------------------------------------
from datetime import datetime

@bp.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    # 1. Grab the pending user ID from the session
    pending_user_id = session.get("pending_voter_id")
    if not pending_user_id:
        flash("Please enter your credentials first.", "warning")
        return redirect(url_for("routes.login"))

    # 2. Load the user
    user = User.query.get(pending_user_id)
    if not user:
        return redirect(url_for("routes.login"))

    form = OTPForm()
    if form.validate_on_submit():
        token_input = form.otp.data
        
        # 3. Check if the OTP is expired (or missing)
        if not user.otp_expiration or datetime.utcnow() > user.otp_expiration:
            flash("Your verification code has expired. Please log in again to receive a new one.", "danger")
            session.pop("pending_voter_id", None) # Clean up session
            return redirect(url_for("routes.login"))
            
        # 4. Check if the OTP is simply incorrect
        if user.otp_token != token_input:
            flash("Incorrect verification code. Please try again.", "danger")
            # We do NOT pop the session or redirect. 
            # We just re-render the page so they can try again.
            return render_template("otp_verify.html", form=form)

        # 5. If correct and not expired, use the model's method to finalize and clear the token from the DB
        if user.verify_otp(token_input):
            login_user(user)
            session.pop("pending_voter_id", None) # Clean up session
            
            flash("Two-factor authentication successful. You may now vote.", "success")
            return redirect(url_for("routes.dashboard"))
            
    return render_template("otp_verify.html", form=form)

# -----------------------------------------
# 4. DASHBOARD (VOTER’S MAIN PAGE)
# -----------------------------------------
from datetime import datetime
from app.models import Election, Vote
@bp.route("/dashboard")
@login_required
def dashboard():
    now = datetime.utcnow()

    # Fetch most recent election and localize for display
    election = Election.query.order_by(Election.id.desc()).first()


    election_ended = False
    has_voted = False

    if election:
        election_ended = election.end_time <= now
        has_voted = Vote.query.filter_by(
            voter_id=current_user.id, election_id=election.id
        ).first() is not None

    return render_template(
        "dashboard.html",
        election=election,
        election_ended=election_ended,
        has_voted=has_voted,
        now=now,
    )


@bp.route("/vote", methods=["GET"])
@login_required
def vote():
    now = datetime.utcnow()
    election = Election.query.filter(
        Election.start_time <= now, 
        Election.end_time > now
    ).order_by(Election.id.desc()).first()
    

    if not election:
        flash("No active election.", "warning")
        return redirect(url_for("routes.dashboard"))

    if not (election.start_time <= now <= election.end_time):
        flash("Election is not currently active.", "warning")
        return redirect(url_for("routes.dashboard"))
    
    if current_user.is_admin: # (Or current_user.role == 'admin')
        flash("Administrators are not permitted to cast votes.", "danger")
        return redirect(url_for('dashboard'))

    has_voted = Vote.query.filter_by(
        voter_id=current_user.id, election_id=election.id
    ).first() is not None

    if has_voted:
        flash("You have already voted.", "info")
        return redirect(url_for("routes.dashboard"))

    # Dynamic form
    from wtforms import SelectField
    class DynamicVoteForm(VoteForm):
        pass

    designations = (
        db.session.query(Candidate.designation)
        .distinct()
        .order_by(Candidate.designation)
        .all()
    )
    designations = [d[0] for d in designations]

    for desig in designations:
        candidates = Candidate.query.filter_by(designation=desig).all()
        choices = [(0, "– Leave Blank –")] + [(c.id, c.user.full_name) for c in candidates]
        setattr(DynamicVoteForm, f"vote_for_{desig.replace(' ', '_')}",
                SelectField(desig, choices=choices, coerce=int))

    form = DynamicVoteForm()
    abi, _ = compile_contract()
    abi_json = abi

    return render_template("vote.html", form=form, election=election, now=now, abi_json=abi_json)


# -----------------------------------------
# 5. ADMIN PANEL
# -----------------------------------------
@bp.route("/admin", methods=["GET"])
@login_required
def admin_panel():
    if not session.get("is_admin"):
        return redirect(url_for("routes.login"))

    from sqlalchemy import and_
    from app.models import User, Candidate, Election
    from datetime import datetime

    # Counts
    total_forms = User.query.filter(
        and_(User.is_eligible_voter == False, User.email != "admin@university.com")
    ).count()
    total_candidates = Candidate.query.count()
    total_voters = User.query.filter_by(is_eligible_voter=True).count()

    election = Election.query.order_by(Election.id.desc()).first()
    if election:
        election.check_active()
    now = datetime.utcnow()

    # Flags
    election_status = {
        "ongoing": False,
        "not_started": False,
        "closed": False
    }
    
    show_latest_stats_button = False
    voter_turnout = {
        "voted": 0,
        "remaining": 0
    }
    
    if election:
        election.check_active()
        if election.start_time > now:
                election_status["not_started"] = True
        elif election.is_active: # Use the checked status
                election_status["ongoing"] = True
                # Calculate turnout if ongoing
                voted_ids = {v.voter_id for v in Vote.query.filter_by(election_id=election.id).all()}
                eligible_voters_count = User.query.filter(User.is_eligible_voter==True, User.email != "admin@university.com").count()
                voter_turnout["voted"] = len(voted_ids)
                voter_turnout["remaining"] = eligible_voters_count - len(voted_ids)
        elif election.is_closed: # Use the checked status
                election_status["closed"] = True
                # ✅ CHECK if the closed election has been archived
                is_archived = ElectionStatisticsArchive.query.filter_by(election_id=election.id).count() > 0
                if is_archived:
                    show_latest_stats_button = True # Enable button only if closed AND archived


    return render_template(
        "admin_panel.html",
        total_forms=total_forms,
        total_candidates=total_candidates,
        total_voters=total_voters,
        election=election, # Pass the latest election object
        election_status=election_status,
        voter_turnout=voter_turnout,
        show_latest_stats_button=show_latest_stats_button # ✅ Pass the new flag
    )
    
# In voting_system/app/routes.py (preferably after the admin_panel route)

@bp.route("/admin/live_voters")
@login_required
def live_voters():
    if not session.get("is_admin"):
        abort(403)

    now = datetime.utcnow()
    # Find the current, active election
    election = Election.query.filter(Election.start_time <= now, Election.end_time > now).order_by(Election.id.desc()).first()

    if not election:
        flash("There is no ongoing election to monitor.", "info")
        return redirect(url_for("routes.admin_panel"))

    # [cite_start]Get all eligible voters, excluding the admin [cite: 1006]
    all_eligible_voters = User.query.filter(
        User.is_eligible_voter == True,
        User.email != "admin@university.com"
    ).all()

    # [cite_start]Get the IDs of users who have already voted in this election [cite: 617-622]
    voted_user_ids = {v.voter_id for v in Vote.query.filter_by(election_id=election.id).all()}

    voted_users = [v for v in all_eligible_voters if v.id in voted_user_ids]
    remaining_users = [v for v in all_eligible_voters if v.id not in voted_user_ids]

    return render_template(
        "live_voters.html",
        election=election,
        voted_users=voted_users,
        remaining_users=remaining_users
    )



# 5.1 SHOW RECEIVED FORMS
@bp.route("/admin/show_forms")
@login_required
def show_forms():
    if not session.get("is_admin"):
        return redirect(url_for("routes.login"))

    from app.models import User
    from flask_wtf.csrf import generate_csrf

    # ✅ Only users who are not admin and not approved yet
    users = User.query.filter(
        User.is_eligible_voter == False,
        User.email != "admin@university.com"
    ).all()

    return render_template(
        "eligibility_form.html",
        users=users,
        csrf_token=generate_csrf()
    )





# 5.2 ADD CANDIDATES
@bp.route("/admin/add_candidate", methods=["GET", "POST"])
@login_required
def add_candidate():
    if not session.get("is_admin"):
        return redirect(url_for("routes.login"))
    # Show list of users marked as is_candidate=True but not yet in Candidate table
    eligible_candidates = User.query.filter_by(is_candidate=True).all()
    # Exclude those already in Candidate table
    candidate_user_ids = {c.user_id for c in Candidate.query.all()}
    choices = [(u.id, u.full_name + " (" + u.designation + ")") for u in eligible_candidates if u.id not in candidate_user_ids]

    form = AddCandidateForm()
    form.user_id.choices = choices

    if form.validate_on_submit():
        selected_user = User.query.get(form.user_id.data)
        new_candidate = Candidate(
            user_id=selected_user.id,
            designation=form.designation.data,
        )
        db.session.add(new_candidate)
        db.session.commit()
        flash(f"{selected_user.full_name} added as candidate for {form.designation.data}", "success")
        return redirect(url_for("routes.add_candidate"))
    
    from collections import defaultdict
    all_candidates = Candidate.query.all()
    grouped_candidates = defaultdict(list)
    for c in all_candidates:
        grouped_candidates[c.designation].append(c)
    
    return render_template("add_candidate.html", form=form, grouped_candidates=grouped_candidates)




@bp.route("/admin/add_voter", methods=["GET", "POST"])
@login_required
def add_voter():
    if not current_user.is_admin: 
        return redirect(url_for("routes.login"))

    # 1. Initialize Forms
    assign_form = AssignDesignationForm()
    form = AddVoterForm()

    users = User.query.filter(User.is_eligible_voter == False, User.email != "admin@university.com").all()
    form.user_id.choices = [(u.id, f"{u.full_name} ({u.email})") for u in users]

    # --- NEW STRICT CHECK: Block modification if election is active ---
    latest_election = Election.query.order_by(Election.id.desc()).first()
    if latest_election:
        now = datetime.utcnow()
        if latest_election.start_time <= now < latest_election.end_time:
            if request.method == "POST":
                flash("❌ Cannot add or modify voters while an election is actively in progress.", "danger")
                return redirect(url_for("routes.add_voter"))

    # 2. Handle 'Assign Designation' Form (Update Roles)
    if 'submit_assign' in request.form:
        if assign_form.validate_on_submit():
            designation = assign_form.designation.data
            user_ids_to_assign = request.form.getlist("user_ids")
            
            if not user_ids_to_assign:
                flash("You must select at least one user to assign.", "warning")
                return redirect(url_for("routes.add_voter"))

            latest_election = Election.query.order_by(Election.id.desc()).first()
            
            # Allow assigning roles even if no election is active (optional, based on your logic)
            # if not latest_election: ...

            count = 0
            for user_id in user_ids_to_assign:
                user = User.query.get(user_id)
                if user and user.email != "admin@university.com":
                    user.designation = designation
                    user.is_candidate = True
                    
                    # Link to election if one exists
                    if latest_election:
                        candidate = Candidate.query.filter_by(
                            user_id=user.id, 
                            election_id=latest_election.id
                        ).first()
                        
                        if candidate:
                            candidate.designation = designation
                        else:
                            new_candidate = Candidate(
                                user_id=user.id,
                                designation=designation,
                                election_id=latest_election.id
                            )
                            db.session.add(new_candidate)
                    
                    count += 1
            
            db.session.commit()
            flash(f"Successfully assigned '{designation}' to {count} user(s).", "success")
            return redirect(url_for("routes.add_voter"))

    # 3. Handle 'Add Voter' Form (Single User Enable)
    # We check 'submit' name specifically to distinguish from the other form
    if 'submit' in request.form and form.validate_on_submit():
        user = User.query.get(form.user_id.data)
        if user:
            user.is_eligible_voter = True
            # Optional: Generate password if needed
            # new_password = os.urandom(6).hex()
            # user.set_password(new_password)
            db.session.commit()
            flash(f"{user.full_name} marked as eligible voter.", "success")
        return redirect(url_for("routes.add_voter"))
    
    # 4. Render Page (GET Request)
    eligible_voters = User.query.filter(
        User.is_eligible_voter == True
    ).order_by(User.full_name).all()
    
    from flask_wtf.csrf import generate_csrf
    csrf_token = generate_csrf()
    
    return render_template(
        "add_voter.html", 
        form=form, 
        voters=eligible_voters, 
        csrf_token=csrf_token,
        assign_form=assign_form
    )

# 5.4 ASSIGN ELECTION DATE & TIME (DEPLOY CONTRACT)
# In voting_system/app/routes.py

# (Make sure these imports are present at the top)
from app.blockchain import load_contract_instance, send_signed_transaction
from web3 import Web3

# ... (rest of imports) ...

@bp.route("/admin/assign_election", methods=["GET", "POST"])
@login_required
def assign_election():
    if not session.get("is_admin"):
        return redirect(url_for("routes.login"))

    form = AssignElectionForm()
    last_election = Election.query.order_by(Election.id.desc()).first()

    if form.validate_on_submit():
        new_election = None
        try:
            # Step 1 & 2: Deploy contract, Convert time (existing code)
            contract_address, abi = deploy_contract()
            # ... (time conversion code) ...

            # Step 3: Create and save the new election to get its ID
            from pytz import timezone, utc
            pkt = timezone("Asia/Karachi")
            start_pkt = pkt.localize(form.start_datetime.data)
            end_pkt = pkt.localize(form.end_datetime.data)
            start_utc = start_pkt.astimezone(utc)
            end_utc = end_pkt.astimezone(utc)
            new_election = Election(
                title=form.title.data,
                start_time=start_utc,
                end_time=end_utc,
                is_active=False,
                contract_address=contract_address,
            )
            db.session.add(new_election)
            db.session.commit()

            # --- Step 4: Register Candidates and Voters on the Blockchain ---
            try:
                w3, contract = load_contract_instance(contract_address)
                
                # ✅ SECURE: Fetch admin address safely without evaluating w3.eth.accounts[0] immediately
                admin_env = os.getenv("ADMIN_ACCOUNT")
                admin_addr = Web3.to_checksum_address(admin_env) if admin_env else Web3.to_checksum_address(w3.eth.accounts[0])
                
                admin_private_key = os.getenv("ADMIN_PRIVATE_KEY")

                
                if not admin_private_key:
                    raise Exception("ADMIN_PRIVATE_KEY is not set.")

                # --- Register Candidates (Existing Code) ---
                patch_candidates_to_latest_election(new_election.id)
                candidates_to_register = Candidate.query.filter_by(election_id=new_election.id).order_by(Candidate.id).all()
                current_nonce = w3.eth.get_transaction_count(admin_addr)
                
                print(f"Starting candidate registration with nonce {current_nonce}")
                for index, candidate in enumerate(candidates_to_register):
                    placeholder_address = "0x0000000000000000000000000000000000000000"
                    txn = contract.functions.addCandidate(new_election.id, placeholder_address).build_transaction({
                        'chainId': w3.eth.chain_id, 'gas': 200000, 'gasPrice': w3.eth.gas_price,
                        'from': admin_addr, 'nonce': current_nonce + index
                    })
                    receipt = send_signed_transaction(w3, txn)
                    candidate.contract_cid = index
                    print(f"Registered Candidate DB ID {candidate.id} with Contract CID {index} using nonce {current_nonce + index}")
                
                db.session.flush() # Flush candidate updates before proceeding

                # --- ✅ START: Register Eligible Voters ---
                eligible_voters = User.query.filter(
                    User.is_eligible_voter == True,
                    User.email != "admin@university.com" # Exclude admin
                ).all()
                
                # Continue nonce incrementing from where candidate registration left off
                voter_start_nonce = current_nonce + len(candidates_to_register)
                print(f"Starting voter registration with nonce {voter_start_nonce}")

                for index, voter in enumerate(eligible_voters):
                    voter_id_on_chain = voter.id # Use the user's database ID as the voterId
                    
                    # Build transaction to call addVoterById
                    txn_voter = contract.functions.addVoterById(new_election.id, voter_id_on_chain).build_transaction({
                        'chainId': w3.eth.chain_id, 'gas': 100000, 'gasPrice': w3.eth.gas_price,
                        'from': admin_addr, 'nonce': voter_start_nonce + index # Increment nonce
                    })
                    
                    # Sign and send
                    receipt_voter = send_signed_transaction(w3, txn_voter)
                    print(f"Registered Voter DB ID {voter.id} on contract using nonce {voter_start_nonce + index}")
                    
                # --- ✅ END: Register Eligible Voters ---

                db.session.commit() # Commit candidate contract_cids and potentially other changes

            except Exception as contract_err:
                # Rollback and delete the election if blockchain registration fails
                db.session.rollback()
                # Use the 'new_election' object captured earlier
                if new_election:
                   election_to_delete = db.session.get(Election, new_election.id) # Use db.session.get for safety
                   if election_to_delete:
                       db.session.delete(election_to_delete)
                       db.session.commit()
                flash(f"❌ Blockchain error: Failed to register candidates/voters. Election rolled back. Details: {str(contract_err)}", "danger")
                current_app.logger.error(f"Candidate/Voter registration failed, election rolled back: {str(contract_err)}")
                return redirect(url_for("routes.assign_election"))
            # --- End Candidate/Voter Registration Block ---

            # Step 5: Save contract address in config
            current_app.config["CONTRACT_ADDRESS"] = contract_address

            flash(f"✅ Election scheduled! Contract deployed. {len(candidates_to_register)} candidates and {len(eligible_voters)} voters registered on blockchain.", "success")
            return redirect(url_for("routes.admin_panel"))

        except Exception as e:
            # Catch general errors
            db.session.rollback()
            if new_election and db.session.object_session(new_election):
                 election_to_delete = db.session.get(Election, new_election.id)
                 if election_to_delete:
                    db.session.delete(election_to_delete)
                    db.session.commit()
            flash(f"❌ An unexpected error occurred during election setup: {str(e)}", "danger")
            current_app.logger.error(f"General election assignment failed: {str(e)}")

    return render_template("assign_election.html", form=form)


@bp.route("/admin/send_credentials", methods=["GET", "POST"])
@login_required
def send_credentials():
    if not session.get("is_admin"):
        return redirect(url_for("routes.login"))

    unsent_users = User.query.filter_by(is_eligible_voter=True, credentials_sent=False)\
                             .filter(User.email != "admin@university.com").all()
    sent_users = User.query.filter_by(is_eligible_voter=True, credentials_sent=True)\
                           .filter(User.email != "admin@university.com").all()

    if request.method == "POST":
        action = request.form.get("action")
        selected_ids = request.form.getlist("selected_ids")
        count = 0

        if action == "send_all":
            users = unsent_users
        elif action == "resend_all":
            users = sent_users
        elif action == "send_selected":
            users = User.query.filter(User.id.in_(selected_ids)).all()
            users = [u for u in users if u in unsent_users]
        elif action == "resend_selected":
            users = User.query.filter(User.id.in_(selected_ids)).all()
            users = [u for u in users if u in sent_users]
        else:
            users = []

        for user in users:
            try:
                user.send_credentials_email()
                count += 1
            except Exception as e:
                print(f"Error sending to {user.email}: {e}")

        if action.startswith("send"):
            flash(f"✅ Credentials sent to {count} user(s).", "success")
        elif action.startswith("resend"):
            flash(f"🔁 Credentials resent to {count} user(s).", "info")

        return redirect(url_for("routes.send_credentials"))

    return render_template(
        "send_credentials.html",
        unsent_users=unsent_users,
        sent_users=sent_users
    )





# -----------------------------------------
# 10. LOGOUT
# -----------------------------------------
@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("routes.index"))


# -----------------------------------------
# 10. Approve user as eligible voter
# -----------------------------------------
# In voting_system/app/routes.py

@bp.route("/admin/approve_pending/<int:user_id>", methods=["POST"])
@login_required
def approve_pending(user_id):
    if not current_user.is_admin:
        abort(403)

    user = User.query.get_or_404(user_id)

    if user.email == "admin@university.com":
        flash("❌ Cannot approve admin as eligible voter.", "danger")
        return redirect(url_for("routes.show_forms"))

    # Set default designation if missing
    if not user.designation:
        user.designation = "Voter"

    # --- UPDATED CHECK ---
    # Block approval ONLY if an election is currently ongoing
    latest_election = Election.query.order_by(Election.id.desc()).first()
    if latest_election:
        now = datetime.utcnow()
        # Check if 'now' is strictly between start and end time
        if latest_election.start_time <= now < latest_election.end_time:
            flash("⚠️ Cannot approve new users while an election is actively in progress.", "warning")
            return redirect(url_for("routes.show_forms"))
        # REMOVED: The check for 'votes_exist' after election end is no longer needed.

    # --- Proceed with Approval ---
    user.is_eligible_voter = True

    # Auto-register as candidate if applicable (and an election exists)
    if user.designation and user.designation.lower() != "voter" and latest_election:
        existing = Candidate.query.filter_by(
            user_id=user.id,
            election_id=latest_election.id # Check specifically for this election
            ).first()
        if not existing:
            candidate = Candidate(
                user_id=user.id,
                designation=user.designation,
                election_id=latest_election.id,
                # contract_cid will be assigned if a *new* election is created later
                contract_cid=None
            )
            db.session.add(candidate)

    db.session.commit()
    flash(f"✅ {user.full_name} approved as eligible voter.", "success")
    # If they were made a candidate, remind admin to register them if election starts
    if user.is_candidate and user.designation != 'Voter':
         flash(f"ℹ️ {user.full_name} was also marked as a candidate. Ensure voters and candidates are registered on the blockchain when the next election is assigned.", "info")

    return redirect(url_for("routes.show_forms"))





@bp.route("/admin/cancel_pending/<int:user_id>", methods=["POST"])
@login_required
def cancel_pending(user_id):
    if not current_user.is_admin:
        abort(403)

    from flask import request
    user = User.query.get_or_404(user_id)
   

    if user.email == "admin@university.com":
        flash("❌ Cannot cancel the admin user.", "danger")
        return redirect(url_for("routes.show_forms"))

    db.session.delete(user)
    db.session.commit()

    flash(f"❌ {user.full_name}'s request was canceled successfully.", "info")
    return redirect(url_for("routes.show_forms"))





# -----------------------------------------
# 12. Remove eligible voter
# -----------------------------------------
# In voting_system/app/routes.py

@bp.route("/admin/remove_user/<int:user_id>", methods=["POST"])
@login_required
def remove_user(user_id):
    if not session.get("is_admin"):
        abort(403)

    user_to_delete = User.query.get_or_404(user_id)

    # Prevent deletion of the admin account
    if user_to_delete.email == "admin@university.com":
        flash("❌ Cannot remove the admin user.", "danger")
        return redirect(url_for("routes.add_voter"))

    latest_election = Election.query.order_by(Election.id.desc()).first()

    # Check the status of the latest election, if it exists
    if latest_election:
        now = datetime.utcnow()
        is_archived = ElectionStatisticsArchive.query.filter_by(election_id=latest_election.id).count() > 0

        # BLOCK if election is currently ongoing
        if latest_election.start_time <= now < latest_election.end_time:
            flash("❌ Cannot remove users while an election is in progress.", "danger")
            return redirect(url_for("routes.add_voter"))

        # BLOCK if election is over but NOT archived
        if now >= latest_election.end_time and not is_archived:
            flash("⚠️ The last election has ended. Please archive its results before removing users.", "warning")
            return redirect(url_for("routes.show_results"))

    # --- PROCEED WITH DELETION ---
    # This block runs if no election exists, or if the last election is safely archived.
    # In voting_system/app/routes.py, inside the remove_user function

    # --- PROCEED WITH DELETION ---
    try:
        # Step 1: Find all Candidate records associated with this user
        candidate_records = Candidate.query.filter_by(user_id=user_to_delete.id).all()
        
        # Step 2: For each Candidate record, delete associated Vote records FIRST
        for cand in candidate_records:
            Vote.query.filter_by(candidate_id=cand.id).delete()
            
        # Step 3: Now delete the Candidate records themselves
        for cand in candidate_records:
            db.session.delete(cand)
            
        # Step 4: Delete any votes cast BY this user (if they were also a voter)
        Vote.query.filter_by(voter_id=user_to_delete.id).delete()

        # Step 5: Finally, delete the User record
        db.session.delete(user_to_delete)
        
        db.session.commit() # Commit all changes
        
        flash(f"🗑️ User '{user_to_delete.full_name}' and all associated election data (candidacies, votes) have been removed.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ A database error occurred while trying to remove the user: {str(e)}", "danger")
        current_app.logger.error(f"Failed to delete user {user_id}: {str(e)}")

    return redirect(url_for("routes.add_voter"))



 






@bp.route("/admin/clear_live_results/<int:election_id>", methods=["POST"])
@login_required
def clear_live_results(election_id):
    if not session.get("is_admin"):
        return redirect(url_for("routes.login"))

    from app.models import Vote, Election
    from flask import flash, redirect, url_for

    election = Election.query.get_or_404(election_id)

    try:
        # ✅ Delete only votes — leave candidates/users intact
        votes_deleted = Vote.query.filter_by(election_id=election_id).count()
        db.session.query(Vote).filter_by(election_id=election_id).delete()

        db.session.commit()

        flash(f"🧹 Cleared {votes_deleted} vote(s) for election '{election.title}' (ID: {election.id}).", "success")
        return redirect(url_for("routes.show_results"))

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Failed to clear votes: {str(e)}", "danger")
        current_app.logger.error(f"Live vote clearing failed for election {election_id}: {str(e)}")
        return redirect(url_for("routes.show_results"))













@bp.route("/api/record_vote", methods=["POST"])
@login_required
def api_record_vote():
    from app.models import Candidate
    from app.blockchain import load_contract_instance, cast_vote_as_admin
    try:
        payload = request.get_json()
        votes = payload.get("votes", {})   # map: designation -> candidate_db_id
        # voter_address no longer required; we use current_user.id as voter_id
        election = Election.query.order_by(Election.start_time.desc()).first()
        if not election:
            return {"error": "No active election."}, 400

        # Prevent double voting (DB-level check)
        already_voted = Vote.query.filter_by(voter_id=current_user.id, election_id=election.id).first()
        if already_voted:
            return {"error": "You have already voted."}, 400

        # Map to contract candidate ids
        contract_ids = []
        db_candidate_ids_voted_for = [] # Store DB IDs for local Vote record

        for designation, candidate_id in votes.items(): # candidate_id is the DB ID from the form
            candidate = Candidate.query.get(candidate_id)

            # ✅ Check if candidate exists and has a contract_cid assigned
            if not candidate or candidate.contract_cid is None:
                db.session.rollback() # Important: undo any previous Vote additions
                return {"error": f"Invalid candidate selection or candidate DB ID {candidate_id} is not registered on the current contract."}, 400

            # ✅ Use candidate.contract_cid for blockchain transaction
            contract_ids.append(candidate.contract_cid)
            db_candidate_ids_voted_for.append(candidate.id) # Keep DB ID for local record

        # Create local Vote records AFTER verifying all candidates are valid
        for db_cid in db_candidate_ids_voted_for:
            new_vote = Vote(voter_id=current_user.id, candidate_id=db_cid, election_id=election.id)
            db.session.add(new_vote)

        db.session.commit()

        # Submit on-chain using admin account
        w3, contract = load_contract_instance(election.contract_address)
        # Use helper that signs with ADMIN_PRIVATE_KEY if present
        receipt_or_txn = cast_vote_as_admin(contract, w3, election.id, current_user.id, contract_ids)

        # If server signed and sent, receipt_or_txn is receipt; otherwise it's unsigned txn
        if isinstance(receipt_or_txn, dict) or hasattr(receipt_or_txn, 'transactionHash'):
            # Receipt returned
            return {"status": "ok", "receipt": str(receipt_or_txn)}, 200
        else:
            # unsigned txn returned to be signed by admin
            return {"txn": receipt_or_txn}, 200

    except Exception as e:
        db.session.rollback()
        return {"error": f"Server error: {str(e)}"}, 500








# In app/routes.py
@bp.route('/election_statistics/<int:election_id>')
@login_required
def view_statistics(election_id):
    from collections import defaultdict
    from app.models import Election, Vote, Candidate, User
    from flask import render_template, flash, redirect, url_for

    election = Election.query.get_or_404(election_id)

    if not election.is_closed:
        flash("📊 Statistics are available only after the election ends.", "warning")
        return redirect(url_for("routes.dashboard"))

    # ✅ Only candidates from this election
    candidates = Candidate.query.filter_by(election_id=election.id).all()
    if not candidates:
        flash("⚠️ No candidates found for this election.", "warning")
        return redirect(url_for("routes.admin_panel"))

    # ✅ Total eligible voters (assumed constant across elections)
    total_voters = User.query.filter(
        User.is_eligible_voter == True,
        User.email != "admin@university.com"
    ).count()

    # ✅ Group by designation
    designation_stats = defaultdict(lambda: {
        "total_voters": total_voters,
        "votes_cast": 0,
        "turnout": 0,
        "candidates": []
    })

    for candidate in candidates:
        # ✅ Only count votes cast in this election
        vote_count = Vote.query.filter_by(candidate_id=candidate.id, election_id=election.id).count()
        desig = candidate.designation
        stat = designation_stats[desig]
        stat["votes_cast"] += vote_count
        stat["candidates"].append({
            "name": candidate.user.full_name,
            "votes": vote_count
        })

    for stat in designation_stats.values():
        if stat["total_voters"] > 0:
            stat["turnout"] = round((stat["votes_cast"] / stat["total_voters"]) * 100, 2)

    return render_template(
        "election_statistics.html",
        election=election,
        designation_stats=designation_stats
    )










# In app/routes.py
# Updated /export_pdf/<int:election_id> route to serve data from archive if exists
@bp.route("/export_pdf/<int:election_id>")
@login_required
def export_pdf(election_id):
    from app.models import Election, Vote, Candidate, ElectionStatisticsArchive, User
    from flask import render_template, Response
    from weasyprint import HTML
    from collections import defaultdict
    from datetime import datetime
    from pathlib import Path

    election = Election.query.get_or_404(election_id)

    # 🧠 Check if archived statistics exist for this election
    archived_entries = ElectionStatisticsArchive.query.filter_by(election_id=election.id).all()

    results = defaultdict(list)

    if archived_entries:
        # ✅ Use archived data
        for entry in archived_entries:
            results[entry.designation].append((None, entry.candidate_name, entry.vote_count))

        for designation in results:
            results[designation].sort(key=lambda x: x[2], reverse=True)
    else:
        # ✅ Fallback to live data if no archive
        candidates = Candidate.query.filter_by(election_id=election.id).all()
        for c in candidates:
            vote_count = Vote.query.filter_by(candidate_id=c.id, election_id=election.id).count()
            results[c.designation].append((c.id, c.user.full_name, vote_count))

        for designation in results:
            results[designation].sort(key=lambda x: x[2], reverse=True)

    # 🖼 Logo path for WeasyPrint
    logo_path = Path("static/images/university_logo.jpg").resolve().as_uri()

    html = render_template(
        "export_pdf.html",
        results=results,
        election=election,
        now=datetime.utcnow(),
        logo_url=logo_path
    )

    pdf = HTML(string=html).write_pdf()
    filename = election.title.replace(" ", "_") if election.title else f"Election_{election.id}"
    response = Response(pdf, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}.pdf"
    return response





@bp.route("/admin/elections_history")
@login_required
def elections_history():
    if not session.get("is_admin"):
        return redirect(url_for("routes.login"))

    # Show elections that have archived data
    archived_ids = db.session.query(ElectionStatisticsArchive.election_id).distinct().all()
    archived_ids = [eid[0] for eid in archived_ids]

    elections = Election.query.filter(Election.id.in_(archived_ids)).order_by(Election.id.desc()).all()
    return render_template("elections_history.html", elections=elections)





@bp.route("/admin/delete_election/<int:election_id>", methods=["POST"])
@login_required
def delete_election(election_id):
    if not current_user.is_admin:
        abort(403)

    try:
        latest_election = Election.query.order_by(Election.id.desc()).first()
        if latest_election and latest_election.id == election_id:
            flash("⚠️ Cannot delete the latest election. Please create a new election first.", "warning")
            return redirect(url_for("routes.elections_history"))

        # Safe to delete
        Vote.query.filter_by(election_id=election_id).delete()
        Candidate.query.filter_by(election_id=election_id).delete()
        ElectionStatisticsArchive.query.filter_by(election_id=election_id).delete()
        Election.query.filter_by(id=election_id).delete()

        db.session.commit()
        flash("🗑️ Archived election deleted successfully.", "success")
        return redirect(url_for("routes.elections_history"))

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Deletion failed: {str(e)}", "danger")
        current_app.logger.error(f"Election deletion failed: {str(e)}")
        return redirect(url_for("routes.elections_history"))






# In voting_system/app/routes.py
# In voting_system/app/routes.py

# In voting_system/app/routes.py

@bp.route("/admin/results", methods=["GET"])
@login_required
def show_results():
    if not session.get("is_admin"):
        return redirect(url_for("routes.login"))

    election = Election.query.order_by(Election.id.desc()).first()
    if not election:
        flash("No election has been defined yet.", "warning")
        return redirect(url_for("routes.admin_panel"))

    now = datetime.utcnow()
    election.check_active() # Ensure status is up-to-date

    # # --- Debugging ---
    # print(f"--- Debugging /admin/results ---")
    # print(f"Latest Election ID: {election.id}")
    # print(f"Election is_closed: {election.is_closed}")
    # print(f"Election is_active: {election.is_active}")
    # # --- End Debugging ---

    # --- STATE 1: ELECTION IS CLOSED ---
    if election.is_closed:
        archived_entries = ElectionStatisticsArchive.query.filter_by(election_id=election.id).all()

        # # --- Debugging ---
        # print(f"Found {len(archived_entries)} archive entries for election {election.id}")
        # # --- End Debugging ---

        if not archived_entries:
            flash("The election has ended. Please ensure the archive process has completed.", "info")
            return render_template(
                "results.html",
                election=election,
                results=None, # Explicitly None
                election_active=False,
                election_ended=True,
                now=now
            )

        # Process archived data...
        leaderboard = defaultdict(list)
        for entry in archived_entries:
            leaderboard[entry.designation].append((entry.candidate_name, entry.vote_count))
        for designation in leaderboard:
            leaderboard[designation].sort(key=lambda x: x[1], reverse=True)

        # # --- Debugging ---
        # print(f"Processed leaderboard: {dict(leaderboard)}") # Convert defaultdict for printing
        # # --- End Debugging ---

        return render_template(
            "results.html",
            election=election,
            results=leaderboard, # Should contain data
            election_active=False,
            election_ended=True,
            now=now
        )

    # --- STATE 2: ELECTION IS ACTIVE ---
    elif election.is_active:
        print("Rendering results page: Election is active.") # Debugging
        return render_template(
            "results.html",
            election=election,
            results=None,
            election_active=True,
            election_ended=False,
            now=now
        )

    # --- STATE 3: ELECTION HAS NOT STARTED YET ---
    else: # (now < election.start_time)
        print("Rendering results page: Election has not started.") # Debugging
        return render_template(
            "results.html",
            election=election,
            results=None,
            election_active=False,
            election_ended=False,
            now=now
        )

@bp.route("/admin/archive_statistics/<int:election_id>", methods=["POST"])
@login_required
def archive_statistics(election_id):
    if not session.get("is_admin"):
        abort(403)

    try:
        from app.utils.statistics import archive_statistics_from_blockchain
        archive_statistics_from_blockchain(election_id)
        flash("✅ Results archived successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Failed to archive: {e}", "danger")

    return redirect(url_for("routes.show_results"))


@bp.route('/archived_statistics/<int:election_id>')
@login_required
def archived_statistics(election_id):
    from collections import defaultdict
    from app.models import Election, ElectionStatisticsArchive
    from flask import render_template, flash, redirect, url_for

    election = Election.query.get_or_404(election_id)

    entries = ElectionStatisticsArchive.query.filter_by(election_id=election.id).all()

    if not entries:
        flash("📭 No archived statistics found for this election.", "warning")
        return redirect(url_for("routes.elections_history"))

    # ✅ Structure data
    designation_stats = defaultdict(lambda: {
        "total_voters": 0,
        "votes_cast": 0,
        "turnout": 0,
        "candidates": []
    })

    for entry in entries:
        stat = designation_stats[entry.designation]
        stat["total_voters"] = entry.total_voters
        stat["votes_cast"] += entry.vote_count
        stat["candidates"].append({
            "name": entry.candidate_name,
            "votes": entry.vote_count
        })

    for stat in designation_stats.values():
        if stat["total_voters"] > 0:
            stat["turnout"] = round((stat["votes_cast"] / stat["total_voters"]) * 100, 2)

    return render_template(
        "election_statistics.html",
        election=election,
        designation_stats=designation_stats
    )


@bp.route("/admin/upload_csv", methods=["GET", "POST"])
@login_required
def upload_csv():
    if not session.get("is_admin"):
        abort(403)
    
    form = CSVUploadForm()
    if form.validate_on_submit():
        file = form.csv_file.data
        stream = io.TextIOWrapper(file.stream, encoding="utf-8")
        reader = csv.DictReader(stream)
        
        success_count = 0
        error_count = 0
        errors = []

        for row_num, row in enumerate(reader, 2): # Start from line 2
            try:
                full_name = row['name'].strip()
                email = row['email'].strip()
                phone = row['phone'].strip()
                cnic = row['cnic'].strip()

                # --- Validation ---
                if not all([full_name, email, phone, cnic]):
                    errors.append(f"Row {row_num}: Missing data.")
                    error_count += 1
                    continue
                if len(cnic) != 13 or not cnic.isdigit():
                    errors.append(f"Row {row_num}: CNIC '{cnic}' must be 13 digits.")
                    error_count += 1
                    continue
                
                # --- NEW: Added User.phone to the duplicate check ---
                existing_user = User.query.filter(
                    (User.email == email) | 
                    (User.cnic == cnic) | 
                    (User.phone == phone)
                ).first()
                
                if existing_user:
                    errors.append(f"Row {row_num}: User with this email, CNIC, or phone ('{phone}') already exists.")
                    error_count += 1
                    continue

                # --- Create User (as pending) ---
                user = User(
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    cnic=cnic,
                    password_hash=generate_password_hash(os.urandom(8).hex()),
                    is_eligible_voter=False,
                    designation="Voter"
                )
                db.session.add(user)
                success_count += 1
            
            except KeyError as e:
                errors = [f"CSV file is missing the required column header: {e}"]
                error_count = row_num - 1 # all rows failed
                success_count = 0
                db.session.rollback() # Undo any partial adds
                break
            except Exception as e:
                errors.append(f"Row {row_num}: An unexpected error occurred - {str(e)}")
                error_count += 1
        
        if success_count > 0:
            db.session.commit()
            flash(f"{success_count} users successfully added. They are now pending approval.", "success")
        if error_count > 0:
            # Show first 3 errors to keep the message clean
            flash(f"Could not process {error_count} rows. Errors: {'; '.join(errors[:3])}...", "danger")

        return redirect(url_for('routes.show_forms'))

    return render_template("upload_csv.html", form=form)


# In voting_system/app/routes.py

@bp.route("/admin/withdraw_designation/<int:user_id>", methods=["POST"])
@login_required
def withdraw_designation(user_id):
    if not session.get("is_admin"):
        abort(403)

    user = User.query.get_or_404(user_id)

    # Check if the user is actually a candidate
    if not user.is_candidate or user.designation == 'Voter':
        flash(f"{user.full_name} is already a regular voter.", "info")
        return redirect(url_for("routes.add_voter"))

    # Find the latest election to potentially remove the candidate record
    latest_election = Election.query.order_by(Election.id.desc()).first()

    try:
        # Revert user status
        user.is_candidate = False
        user.designation = "Voter" # Explicitly set back to Voter

        # If an election exists, find and remove the specific candidate record
        if latest_election:
            candidate_record = Candidate.query.filter_by(
                user_id=user.id,
                election_id=latest_election.id
            ).first()
            if candidate_record:
                db.session.delete(candidate_record)

        db.session.commit()
        flash(f"✅ Designation withdrawn for {user.full_name}. They are now a voter.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ An error occurred while withdrawing designation: {str(e)}", "danger")
        current_app.logger.error(f"Failed to withdraw designation for user {user_id}: {str(e)}")

    return redirect(url_for("routes.add_voter"))


# In voting_system/app/routes.py

@bp.route("/public/election_history")
def public_election_history():
    # [cite_start]Show elections that have archived data [cite: 1542-1543]
    archived_ids = db.session.query(ElectionStatisticsArchive.election_id).distinct().all()
    archived_ids = [eid[0] for eid in archived_ids]

    elections = Election.query.filter(Election.id.in_(archived_ids)).order_by(Election.id.desc()).all()
    # Pass 'is_public=True' to the template to hide admin buttons
    return render_template("elections_history.html", elections=elections, is_public=True)

# In voting_system/app/routes.py

@bp.route("/public/voter_list")
def public_voter_list():
    # [cite_start]Fetch ALL eligible voters (excluding admin) [cite: 1006, 738-739]
    all_eligible_voters = User.query.filter(
        User.is_eligible_voter == True,
        User.email != "admin@university.com"
    ).order_by(User.full_name).all()

    return render_template("public_voter_list.html", voters=all_eligible_voters)

# In voting_system/app/routes.py

@bp.route("/public/candidate_list")
def public_candidate_list():
    # Fetch Candidate List, ordered by designation priority (same logic as index)
    all_candidates = Candidate.query.join(User).order_by(User.full_name).all()
    
    designation_order = [
        "President", "Vice President", "General Secretary",
        "Joint Secretary", "Finance Secretary", "Social Secretary"
    ]
    
    ordered_candidates = {desig: [] for desig in designation_order}
    for c in all_candidates:
        if c.designation in ordered_candidates:
            ordered_candidates[c.designation].append(c.user)
            
    # Filter out empty designations for the template
    ordered_candidates_filtered = {
        desig: users for desig, users in ordered_candidates.items() if users
    }
            
    return render_template("public_candidate_list.html", candidates=ordered_candidates_filtered)

# In voting_system/app/routes.py

@bp.route('/public/statistics/<int:election_id>')
def public_statistics(election_id):
    election = Election.query.get_or_404(election_id)
    
    # Fetch data ONLY from the archive
    entries = ElectionStatisticsArchive.query.filter_by(election_id=election.id).all()

    if not entries:
        flash("📊 Archived statistics are not available for this election.", "warning")
        # Redirect to public history page if stats don't exist
        return redirect(url_for("routes.public_election_history"))

    # Process archived data for display (copied from archived_statistics route)
    designation_stats = defaultdict(lambda: {
        "total_voters": 0,
        "votes_cast": 0,
        "turnout": 0,
        "candidates": []
    })

    for entry in entries:
        stat = designation_stats[entry.designation]
        # Use archive data for consistency
        stat["total_voters"] = entry.total_voters 
        stat["votes_cast"] += entry.vote_count 
        stat["candidates"].append({
            "name": entry.candidate_name,
            "votes": entry.vote_count
        })

    # Calculate turnout based on archived data
    for stat in designation_stats.values():
         # Calculate total votes cast for the designation from candidate votes
        total_designation_votes = sum(c['votes'] for c in stat['candidates'])
        stat["votes_cast"] = total_designation_votes # Ensure votes_cast reflects summed votes
        if stat["total_voters"] > 0:
            stat["turnout"] = round((stat["votes_cast"] / stat["total_voters"]) * 100, 2)
        else:
            stat["turnout"] = 0


    # Render the SAME statistics template, but mark it as public
    return render_template(
        "election_statistics.html",
        election=election,
        designation_stats=designation_stats,
        is_public=True # ✅ Pass flag to control back button
    )
    
    
    # In voting_system/app/routes.py

# Add WeasyPrint and Path if not already imported at the top
from weasyprint import HTML
from pathlib import Path
from flask import Response # Add Response if not imported

@bp.route("/public/export_pdf/<int:election_id>")
def public_export_pdf(election_id):
    # Imports needed within the function
    from app.models import Election, ElectionStatisticsArchive
    from collections import defaultdict
    from datetime import datetime

    election = Election.query.get_or_404(election_id)

    # Fetch ONLY archived statistics for public view
    archived_entries = ElectionStatisticsArchive.query.filter_by(election_id=election.id).all()

    if not archived_entries:
        flash("Cannot export PDF: Archived statistics not found for this election.", "warning")
        # Redirect back to the public history page if archive is missing
        return redirect(url_for('routes.public_election_history'))

    # Process archived data for the PDF template
    results = defaultdict(list)
    for entry in archived_entries:
        # Use tuple format (id, name, votes) expected by export_pdf.html template
        # Use None for id as it's not directly available/needed here
        results[entry.designation].append((None, entry.candidate_name, entry.vote_count))

    # Sort candidates by votes within each designation
    for designation in results:
        results[designation].sort(key=lambda x: x[2], reverse=True)

    # Logo path for WeasyPrint
    try:
        # Ensure correct path resolution relative to the app's static folder
        logo_path = Path(current_app.static_folder) / "images" / "university_logo.png"
        logo_url = logo_path.resolve().as_uri() if logo_path.exists() else None
    except Exception as e:
        current_app.logger.error(f"Error resolving logo path: {e}")
        logo_url = None # Set to None if path resolution fails

    # Render the existing PDF template
    html = render_template(
        "export_pdf.html",
        results=results,
        election=election,
        now=datetime.utcnow(),
        logo_url=logo_url
    )

    # Generate PDF
    try:
        pdf = HTML(string=html).write_pdf()
        filename = election.title.replace(" ", "_") if election.title else f"Election_{election.id}"
        response = Response(pdf, mimetype="application/pdf")
        response.headers["Content-Disposition"] = f"attachment; filename={filename}_Results.pdf"
        return response
    except Exception as e:
        current_app.logger.error(f"Error generating PDF: {e}")
        flash("An error occurred while generating the PDF.", "danger")
        # Redirect back instead of showing an error page
        return redirect(url_for('routes.public_statistics', election_id=election_id))
    
    
    
    
@bp.route("/admin/bulk_approve", methods=["POST"])
@login_required
def bulk_approve_pending():
    if not current_user.is_admin:
        abort(403)
        
    action = request.form.get("action") # 'approve' or 'reject'
    user_ids = request.form.getlist("user_ids")
    
    if not user_ids:
        flash("No users selected.", "warning")
        return redirect(url_for("routes.show_forms"))

    # --- UPDATED CHECK: Block ALL bulk actions during active election ---
    latest_election = Election.query.order_by(Election.id.desc()).first()
    if latest_election:
        now = datetime.utcnow()
        if latest_election.start_time <= now < latest_election.end_time:
            flash("❌ Cannot bulk approve or reject users while an election is actively in progress.", "danger")
            return redirect(url_for("routes.show_forms"))
    # --------------------------------------------------------------------

    count = 0
    users = User.query.filter(User.id.in_(user_ids)).all()

    for user in users:
        if user.email == "admin@university.com": continue
        
        if action == "approve":
            user.is_eligible_voter = True
            
            # Logic to add to Candidate table if needed
            if user.designation and user.designation != 'Voter' and latest_election:
                existing = Candidate.query.filter_by(user_id=user.id, election_id=latest_election.id).first()
                if not existing:
                    cand = Candidate(user_id=user.id, designation=user.designation, election_id=latest_election.id)
                    db.session.add(cand)
            count += 1
            
        elif action == "reject":
            db.session.delete(user)
            count += 1

    db.session.commit()
    flash(f"Successfully {action}ed {count} user(s).", "success")
    return redirect(url_for("routes.show_forms"))


import random
from datetime import datetime
from flask import session, flash, redirect, url_for, render_template
from flask_login import current_user, login_required
from app.utils.email_otp import send_otp_email # Make sure this points to your updated file

@bp.route("/generate_otp", methods=["POST"])
@login_required
def generate_otp():
    # 1. Generate a secure 6-digit OTP
    otp_code = str(random.randint(100000, 999999))
    
    # 2. Store the OTP securely in the user's session
    session['current_otp'] = otp_code
    session['otp_timestamp'] = datetime.utcnow().timestamp() # Optional: for expiration logic
    
    # 3. Send the OTP via Email instead of SMS
    user_email = current_user.email
    success = send_otp_email(user_email, otp_code)
    
    if success:
        flash("An OTP has been sent to your registered email address.", "success")
        return redirect(url_for("routes.otp_verify")) # Redirect to the verification input page
    else:
        flash("System error: Failed to send OTP email. Please try again later.", "danger")
        return redirect(url_for("routes.dashboard"))