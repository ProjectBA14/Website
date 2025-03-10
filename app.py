from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import firebase_admin
from firebase_admin import credentials, auth, storage, firestore
from werkzeug.utils import secure_filename
import os
import secrets
import requests
from firebase_admin.exceptions import FirebaseError  # Use FirebaseError for exceptions
from datetime import datetime, timedelta, timezone
import json

# OAuth libraries
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
from google.auth.exceptions import RefreshError
from google.cloud.firestore_v1 import _helpers


# Generate a secret key for Flask (use a secure key in production)
app_secret_key = secrets.token_hex(16)

# Load the Firebase service account key from the environment variable
service_account_key = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY')

if service_account_key is None:
    raise ValueError("FIREBASE_SERVICE_ACCOUNT_KEY environment variable not set")

try:
    # Convert the JSON string to a dictionary
    service_account_info = json.loads(service_account_key)

    # Initialize the Firebase Admin SDK
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'ayushstartup-7277a.appspot.com',  # Use your Firebase storage bucket
    })

except RefreshError as e:
    print(f"Error initializing Firebase: {e}")
    raise
# Initialize Firestore DB
db = firestore.client()

# Function to set admin claim
def set_admin(uid):
    auth.set_custom_user_claims(uid, {'admin': True})

def set_it_executive(uid):
    auth.set_custom_user_claims(uid, {'it_executive': True})

# Flask app setup
template = "./template"
app = Flask(__name__, template_folder=template)
app.secret_key = app_secret_key
GOOGLE_CLIENT_ID = "1061904780000-0067nfgjcnnsm2jefj0qpitqs5sina9b.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"

# OAuth Flow configuration
flow = Flow.from_client_config(
    {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "project_id": "windy-elevator-437515-p4",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": ['https://ticketing-57ep.onrender.com/callback'],  # Use only the Render URI
        }
    },
    scopes=['https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email', 'openid']
)

# Set the redirect_uri to the Render-specific URI
flow.redirect_uri = 'https://ticketing-57ep.onrender.com/callback'

# Configurations for file uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Helper function to check if the uploaded file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/google_login')
def google_login():
    # The redirect_uri is already set to the Render-specific URI
    authorization_url, state = flow.authorization_url()
    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    try:
        # Fetch the token
        flow.fetch_token(authorization_response=request.url)
    except Exception as e:
        # Provide more details if the token fetch fails
        print(f"Error fetching token: {e}")
        flash(f"Failed to fetch token. Error: {e}", 'error')
        return redirect(url_for('login_page'))

    # Verify the state parameter to prevent CSRF
    if session.get('state') != request.args.get('state'):
        flash("Invalid state parameter.", 'error')
        return redirect(url_for('login_page'))

    credentials = flow.credentials
    request_session = google.auth.transport.requests.Request()

    try:
        # Verify the ID token
        id_info = id_token.verify_oauth2_token(
            id_token=credentials.id_token, request=request_session, audience=GOOGLE_CLIENT_ID
        )
    except ValueError as e:
        # Handle the case where the ID token is invalid
        print(f"Invalid ID token: {e}")
        flash("Failed to verify ID token.", 'error')
        return redirect(url_for('login_page'))

    # Restrict users to only those with a gdgu.org domain
    email = id_info.get('email')
    name = id_info.get('name')
    if email.endswith('@gdgu.org') or email.endswith('@gdgoenka.org'):
        # Add user to the session
        session['user_email'] = email
        session['user_token'] = id_info['sub']

        try:
            # Try to get the user from Firebase
            user = auth.get_user_by_email(email)
        except firebase_admin.auth.UserNotFoundError:
            # If the user doesn't exist, create them in Firebase Authentication
            try:
                user = auth.create_user(
                    email=email,
                    display_name=name,
                    email_verified=True  # Since it's through Google OAuth, we know the email is verified
                )
                flash(f"Account for {email} created successfully!", 'success')
            except Exception as e:
                flash(f"Error creating account for {email}: {str(e)}", 'error')
                return redirect(url_for('login_page'))

        # After user creation or fetching, check if the user is an admin or IT executive
        claims = user.custom_claims
        if claims and claims.get('admin'):
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        elif claims and claims.get('it_executive'):
            session['is_it_executive'] = True
            return redirect(url_for('it_executive_dashboard'))
        else:
            session['is_admin'] = False
            return redirect(url_for('dashboard'))
    else:
        flash("You must use an email from the gdgu.org domain.", 'error')
        return redirect(url_for('login_page'))

# Add more detailed error messages for debugging
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form['username']
        password = request.form['password']

        try:
            # Verify the email and password using Firebase's REST API
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            response = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={'AIzaSyCEUHsjOvi_5AbRgHSTRE0Tgk6QDcFhCoM'}",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"}
            )
            response_data = response.json()

            if 'idToken' not in response_data:
                flash(f"Invalid email or password. Error: {response_data.get('error', 'Unknown error')}", 'error')
                return render_template('login.html')

            # Store the user token and email in the session
            session['user_token'] = response_data['idToken']
            session['user_email'] = email

            # Reset session roles to ensure correct roles are assigned
            session['is_admin'] = False
            session['is_it_executive'] = False

            # Fetch user from Firebase Admin SDK to check custom claims
            user = auth.get_user_by_email(email)
            claims = user.custom_claims
            if claims:
                if claims.get('admin'):
                    session['is_admin'] = True
                    session['user_role'] = 'admin'
                    return redirect(url_for('admin_dashboard'))
                elif claims.get('it_executive'):
                    session['is_it_executive'] = True
                    session['user_role'] = 'it_executive'
                    return redirect(url_for('it_executive_dashboard'))
                else:
                    session['user_role'] = 'user'
                    return redirect(url_for('dashboard'))
            else:
                session['user_role'] = 'user'
                return redirect(url_for('dashboard'))

        except requests.exceptions.RequestException as e:
            flash(f"Error logging in: {str(e)}", 'error')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_token' not in session or not session.get('is_admin'):
        flash("Only admins can access the password change functionality.", 'error')
        return redirect(url_for('login_page'))

    if request.method == 'POST':
        user_email = request.form.get('user_email')
        new_password = request.form.get('new_password')

        if not user_email or not new_password:
            flash("Please provide both the email and new password.", 'error')
            return redirect(url_for('change_password'))

        try:
            # Get the user by email
            user = auth.get_user_by_email(user_email)
            
            # Update the password
            auth.update_user(user.uid, password=new_password)
            flash(f"Password for {user_email} has been changed successfully.", 'success')
        except firebase_admin.auth.UserNotFoundError:
            flash(f"User with email {user_email} does not exist.", 'error')
        except Exception as e:
            flash(f"Error changing password: {str(e)}", 'error')

        return redirect(url_for('change_password'))

    return render_template('change_password.html')


@app.route('/')
def homepage():
    # Ensure the user is logged in
    if 'user_token' not in session:
        flash("Please log in to access the dashboard.")
        return redirect(url_for('login_page'))

    # Determine user role
    user_role = 'user'  # Default role
    if session.get('is_admin'):
        user_role = 'admin'
    elif session.get('is_it_executive'):
        user_role = 'it_executive'

    # Define links based on user role
    role_links = {
        'admin': [
            {'name': 'Homepage', 'url': url_for('homepage')},
            {'name': 'Dashboard', 'url': url_for('dashboard')},
            {'name': 'Admin Dashboard', 'url': url_for('admin_dashboard')},
            {'name': 'Admin Tasks', 'url': url_for('admin_tasks')},
            {'name': 'Admin History', 'url': url_for('ticket_history')}
        ],
        'it_executive': [
            {'name': 'Homepage', 'url': url_for('homepage')},
            {'name': 'Dashboard', 'url': url_for('dashboard')},
            {'name': 'IT Executive Dashboard', 'url': url_for('it_executive_dashboard')},
            {'name': 'Profile', 'url': url_for('profile')},
            {'name': 'Ticket History', 'url': url_for('ticket_history')}
        ],
        'user': [
            {'name': 'Homepage', 'url': url_for('homepage')},
            {'name': 'Dashboard', 'url': url_for('dashboard')},
            {'name': 'Profile', 'url': url_for('profile')},
            {'name': 'Ticket History', 'url': url_for('ticket_history')}
        ]
    }

    # Get links based on the user's role
    allowed_links = role_links.get(user_role, [])

    return render_template('homepage.html', allowed_links=allowed_links, user_role=user_role)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirmPassword']
        recaptcha_response = request.form.get('g-recaptcha-response')

        if password != confirm_password:
            return jsonify({'error': 'Passwords do not match'}), 400

        # Verify reCAPTCHA
        secret_key = 'your-recaptcha-secret-key'
        payload = {
            'secret': secret_key,
            'response': recaptcha_response,
            'remoteip': request.remote_addr
        }
        response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=payload)
        result = response.json()

        try:
            # Create a new user in Firebase Authentication
            user = auth.create_user(email=email, password=password)
            flash("Account created successfully!")
            return jsonify({'success': True, 'redirect': url_for('login_page')}), 200
        except FirebaseError:
            return jsonify({'error': 'Could not complete registration. Email might already be in use.'}), 400
        except Exception as e:
            return jsonify({'error': 'An unexpected error occurred.'}), 400

    return render_template('signup.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_token' not in session:
        flash("Please log in to access the dashboard.")
        return redirect(url_for('login_page'))

    # Fetch the user's profile information from the 'profiles' collection
    user_email = session['user_email']
    user_role = session.get('user_role', 'user')  # Fetch role from session

    profile_ref = db.collection('profiles').document(user_email).get()

    if profile_ref.exists:
        profile_data = profile_ref.to_dict()
    else:
        profile_data = {
            'name': 'Unknown',
            'email': user_email,
            'role': user_role,
            'phone': 'Not available'
        }

    if request.method == 'POST':
        # Debugging: Print the form data
        print("Form data received:", request.form)

        if 'create_ticket' in request.form:
            # Handle normal ticket creation form submission
            title = request.form.get('title')
            product = request.form.get('product')
            issue = request.form.get('issue')
            building = request.form.get('building')
            room = request.form.get('room')
            description = request.form.get('description')
            priority = request.form.get('priority')

            # Validate form data
            if not title or not product or not issue or not building or not room or not description or not priority:
                flash('All fields are required!', 'error')
                return redirect(url_for('dashboard'))

            try:
                # Debugging: Log the data to be saved
                print(f"Creating ticket with data: {title}, {product}, {issue}, {building}, {room}, {description}, {priority}")

                # Create the ticket and store it in Firestore
                ticket_ref = db.collection('tickets').document()
                ticket_ref.set({
                    'title': title,
                    'product': product,
                    'issue': issue,
                    'building': building,
                    'room': room,
                    'description': description,
                    'priority': priority,
                    'status': 'Open',
                    'user_email': user_email,
                    'created_at': firestore.SERVER_TIMESTAMP
                })

                flash('Ticket created successfully!', 'success')
            except FirebaseError as firebase_error:
                flash(f"Firebase error: {firebase_error}", 'error')
                print(f"Firebase error: {firebase_error}")
            except Exception as general_error:
                flash(f"An unexpected error occurred: {general_error}", 'error')
                print(f"Unexpected error: {general_error}")

        elif 'create_scheduling_ticket' in request.form:
            # Handle scheduling ticket creation form submission (only for admin/manager)
            if profile_data.get('role') not in ['admin', 'manager']:
                flash('You do not have permission to create scheduling tickets.', 'error')
                return redirect(url_for('dashboard'))

            event_name = request.form.get('event_name')
            rooms = request.form.get('rooms')
            date = request.form.get('date')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            location = request.form.get('location')
            description = request.form.get('description')
            additional_requirements = request.form.get('additional_requirements')

            # Validate form data for scheduling ticket
            if not all([event_name, rooms, date, start_time, end_time, location, description]):
                flash('All fields are required for scheduling an event!', 'error')
                return redirect(url_for('dashboard'))
            
            try:
                # Debugging: Log the data to be saved
                print(f"Creating scheduling ticket with data: {event_name}, {rooms}, {date}, {start_time}, {end_time}, {location}, {description}")

                # Create the scheduling ticket and store it in Firestore
                event_ref = db.collection('scheduled_events').document()
                event_ref.set({
                    'event_name': event_name,
                    'rooms': rooms,
                    'date': date,
                    'start_time': start_time,
                    'end_time': end_time,
                    'location': location,
                    'description': description,
                    'additional_requirements': additional_requirements,
                    'created_by': user_email,
                    'created_at': firestore.SERVER_TIMESTAMP
                })

                flash('Scheduling ticket created successfully!', 'success')
            except FirebaseError as firebase_error:
                flash(f"Firebase error: {firebase_error}", 'error')
                print(f"Firebase error: {firebase_error}")
            except Exception as general_error:
                flash(f"An unexpected error occurred: {general_error}", 'error')
                print(f"Unexpected error: {general_error}")

        return redirect(url_for('dashboard'))

    # Fetch the user's tickets
    try:
        tickets_ref = db.collection('tickets').where('user_email', '==', user_email).stream()
        tickets = [{'id': ticket.id, **ticket.to_dict()} for ticket in tickets_ref]
        # Debugging: Log the fetched tickets
        print("Fetched tickets:", tickets)
    except FirebaseError as firebase_error:
        flash(f"Firebase error while fetching tickets: {firebase_error}", 'error')
        tickets = []
    except Exception as general_error:
        flash(f"Unexpected error while fetching tickets: {general_error}", 'error')
        tickets = []

    # Fetch scheduled events for admin/manager
    scheduled_events = []
    if user_role in ['admin', 'manager']:
        try:
            events_ref = db.collection('scheduled_events').order_by('date').stream()
            scheduled_events = [{'id': event.id, **event.to_dict()} for event in events_ref]
            # Debugging: Log the fetched events
            print("Fetched scheduled events:", scheduled_events)
        except FirebaseError as firebase_error:
            flash(f"Firebase error while fetching scheduled events: {firebase_error}", 'error')
        except Exception as general_error:
            flash(f"Unexpected error while fetching scheduled events: {general_error}", 'error')

    # Render the dashboard page
    return render_template('dash1.html', tickets=tickets, profile=profile_data, user_role=user_role, scheduled_events=scheduled_events)
@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    # Ensure user is logged in
    if 'user_token' not in session:
        flash("Please log in to create a ticket.", 'error')
        return redirect(url_for('login_page'))

    user_email = session.get('user_email', None)

    # Get form data
    title = request.form.get('title')
    issue = request.form.get('issue')
    building = request.form.get('building')
    room = request.form.get('room')
    description = request.form.get('description')
    priority = request.form.get('priority')

    # Validate data
    if not title or not issue or not building or not room or not description or not priority:
        flash("All fields are required to create a ticket.", 'error')
        return redirect(url_for('dashboard'))

    # Create a ticket document
    ticket_data = {
        'title': title,
        'issue': issue,
        'building': building,
        'room': room,
        'description': description,
        'priority': priority,
        'status': 'Open',  # Initial status of the ticket
        'user_email': user_email,
        'created_at': firestore.SERVER_TIMESTAMP  # Firestore-generated timestamp
    }

    try:
        # Add ticket to Firestore
        db.collection('tickets').add(ticket_data)
        flash("Ticket created successfully!", 'success')
    except Exception as e:
        flash(f"An error occurred while creating the ticket: {e}", 'error')

    return redirect(url_for('dashboard'))

@app.route('/create_scheduling_ticket', methods=['POST'])
def create_scheduling_ticket():
    if 'user_token' not in session:
        flash("Please log in to access this feature.")
        return redirect(url_for('login_page'))

    user_role = session.get('user_role', 'user')
    if user_role not in ['admin', 'manager']:
        flash("You do not have permission to create scheduling tickets.")
        return redirect(url_for('dashboard'))

    # Get form data from the request
    event_name = request.form.get('event_name')
    rooms = request.form.get('rooms')
    date = request.form.get('date')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    location = request.form.get('location')
    description = request.form.get('description')
    additional_requirements = request.form.get('additional_requirements')

    # Validate form data
    if not all([event_name, rooms, date, start_time, end_time, location, description]):
        flash('All fields except additional requirements are required!', 'error')
        return redirect(url_for('dashboard'))

    try:
        # Store the scheduling ticket in Firestore
        event_ref = db.collection('scheduled_events').document()
        event_ref.set({
            'event_name': event_name,
            'rooms': rooms,
            'date': date,
            'start_time': start_time,
            'end_time': end_time,
            'location': location,
            'description': description,
            'additional_requirements': additional_requirements,
            'created_by': session['user_email'],
            'created_at': datetime.utcnow()
        })

        flash('Scheduling ticket created successfully!', 'success')
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'error')

    return redirect(url_for('dashboard'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_token' not in session:
        flash("Please log in to access your profile.")
        return redirect(url_for('login_page'))

    user_email = session['user_email']

    # Fetch user profile data from the 'profiles' collection
    profile_ref = db.collection('profiles').document(user_email)
    profile = profile_ref.get().to_dict()

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        
        # Collect IT executive specific data if the user is an IT executive
        if session.get('is_it_executive'):
            it_level = request.form['it_level']
            department = request.form['department']
            user_data = {
                'name': name,
                'phone': phone,
                'it_level': it_level,
                'department': department
            }
        else:
            user_data = {
                'name': name,
                'phone': phone
            }
        
        # Update or create the profile in the 'profiles' collection
        try:
            profile_ref.set(user_data, merge=True)
            flash("Profile updated successfully!")
        except Exception as e:
            flash(f"An error occurred while updating the profile: {str(e)}", 'error')

    return render_template('profile.html', user=profile)

#It executive dashboard
@app.route('/it_executive_dashboard', methods=['GET', 'POST'])
def it_executive_dashboard():
    if 'user_token' not in session or not session.get('is_it_executive'):
        flash("Please log in to access the IT Executive dashboard.")
        return redirect(url_for('login_page'))

    user_email = session['user_email']

    # Fetch assigned tickets for the IT executive, handle both list and string cases
    assigned_tickets_ref = db.collection('tickets')\
        .where('assigned_to', 'array_contains', user_email).stream()
    assigned_tickets = [{'id': ticket.id, **ticket.to_dict()} for ticket in assigned_tickets_ref]

    # Fetch unassigned (open) tickets
    unassigned_tickets_ref = db.collection('tickets').where('status', '==', 'Open').stream()
    unassigned_tickets = [{'id': ticket.id, **ticket.to_dict()} for ticket in unassigned_tickets_ref]

    # Update the display format for assigned_to to handle both string and list cases
    for ticket in assigned_tickets + unassigned_tickets:
        assigned_to = ticket.get('assigned_to')
        if isinstance(assigned_to, list):
            # Join the list elements if it's an array
            ticket['assigned_to_display'] = ', '.join(assigned_to)
        elif isinstance(assigned_to, str):
            # If it's a string, use it directly
            ticket['assigned_to_display'] = assigned_to
        else:
            # If there's no assigned_to value, mark it as "Unassigned"
            ticket['assigned_to_display'] = 'Unassigned'

    if request.method == 'POST':
        # Handle accepting a ticket (if a ticket ID is provided)
        if 'ticket_id' in request.form:
            ticket_id = request.form.get('ticket_id')
            try:
                # Step 1: Accept ticket, set status to 'In Progress'
                db.collection('tickets').document(ticket_id).update({
                    'assigned_to': firestore.ArrayUnion([user_email]),  # Append the user's email to the list
                    'status': 'In Progress'
                })

                # Step 2: Use Python datetime to generate a timestamp manually
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Step 3: Update history manually with the current timestamp
                db.collection('tickets').document(ticket_id).update({
                    'history': firestore.ArrayUnion([{
                        'status': 'In Progress',
                        'timestamp': current_time,
                        'note': 'Ticket accepted by IT executive'
                    }])
                })
                flash(f'Ticket {ticket_id} accepted!', 'success')
            except Exception as e:
                flash(f'Error accepting ticket: {str(e)}', 'error')

        # Handle updating ticket status
        elif 'update-status' in request.form:
            ticket_id = request.form.get('ticket-id')
            status = request.form.get('ticket-status')
            progress_note = request.form.get('progress-note')

            if ticket_id and status:
                try:
                    ticket_ref = db.collection('tickets').document(ticket_id)

                    # Step 1: Update both the general status field and history
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ticket_ref.update({
                        'status': status,  # Update the main status
                        'history': firestore.ArrayUnion([{
                            'status': status,
                            'timestamp': current_time,
                            'note': progress_note if progress_note else ''
                        }])
                    })
                    flash(f'Ticket {ticket_id} status updated to {status}!', 'success')
                except Exception as e:
                    flash(f'Error updating ticket status: {str(e)}', 'error')

        return redirect(url_for('it_executive_dashboard'))

    # Render the template with the fetched tickets
    return render_template('it_executive_dashboard.html', assigned_tickets=assigned_tickets,
                           unassigned_tickets=unassigned_tickets, user_email=user_email)


# Admin dashboard - promote/demote IT executives and normal users
@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'user_token' not in session or not session.get('is_admin'):
        flash("You must be an admin to access this page.", 'error')
        return redirect(url_for('login_page'))

    # Fetch all IT executives and their current roles
    it_executives_ref = db.collection('it_executives').stream()
    it_executives = []
    for it_exec in it_executives_ref:
        roles = it_exec.to_dict().get('roles', [])
        role = 'Admin' if 'admin' in roles else 'IT Executive' if 'it_executive' in roles else 'Regular User'
        it_executives.append({
            'id': it_exec.id,
            'name': it_exec.get('name'),
            'email': it_exec.get('email'),
            'role': role
        })

    if request.method == 'POST':
        # Handle promotion of a normal user
        if 'promote_user' in request.form:
            user_email = request.form.get('user_email')
            promote_role = request.form.get('promote_role')

            if user_email and promote_role:
                try:
                    # Check if the user exists in Firebase Authentication
                    user = auth.get_user_by_email(user_email)

                    if promote_role == 'admin':
                        db.collection('it_executives').document(user_email).set({
                            'name': user.display_name or user_email,
                            'email': user_email,
                            'roles': firestore.ArrayUnion(['admin'])
                        }, merge=True)
                        auth.set_custom_user_claims(user.uid, {'admin': True})
                        flash(f'{user_email} has been promoted to Admin.', 'success')
                    elif promote_role == 'it_executive':
                        db.collection('it_executives').document(user_email).set({
                            'name': user.display_name or user_email,
                            'email': user_email,
                            'roles': firestore.ArrayUnion(['it_executive'])
                        }, merge=True)
                        auth.set_custom_user_claims(user.uid, {'it_executive': True})
                        flash(f'{user_email} has been promoted to IT Executive.', 'success')
                except firebase_admin.auth.UserNotFoundError:
                    flash(f'User with email {user_email} not found.', 'error')
                except Exception as e:
                    flash(f"Error promoting user: {str(e)}", 'error')

        # Handle promotion/demotion of existing IT executives or demotion to regular user
        elif 'exec_email' in request.form:
            exec_email = request.form.get('exec_email')
            new_role = request.form.get('new_role')

            if exec_email and new_role:
                try:
                    if new_role == 'admin':
                        db.collection('it_executives').document(exec_email).update({'roles': firestore.ArrayUnion(['admin'])})
                        auth.set_custom_user_claims(auth.get_user_by_email(exec_email).uid, {'admin': True})
                        flash(f'{exec_email} has been promoted to Admin.', 'success')
                    elif new_role == 'it_executive':
                        db.collection('it_executives').document(exec_email).update({'roles': firestore.ArrayUnion(['it_executive'])})
                        auth.set_custom_user_claims(auth.get_user_by_email(exec_email).uid, {'it_executive': True})
                        flash(f'{exec_email} has been promoted to IT Executive.', 'success')
                    elif new_role == 'regular_user':
                        # Demote to regular user by clearing all roles
                        db.collection('it_executives').document(exec_email).delete()  # Optional: remove from IT executives collection
                        auth.set_custom_user_claims(auth.get_user_by_email(exec_email).uid, None)  # Clear all roles
                        flash(f'{exec_email} has been demoted to Regular User.', 'success')
                except Exception as e:
                    flash(f"Error updating role: {str(e)}", 'error')

        return redirect(url_for('admin_dashboard'))

    return render_template('admin_dashboard.html', it_executives=it_executives)


@app.route('/admin_tasks', methods=['GET', 'POST'])
def admin_tasks():
    if 'user_token' not in session or not session.get('is_admin'):
        flash("Unauthorized access.")
        return redirect(url_for('login_page'))

    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end_of_today = now.replace(hour=16, minute=0, second=0, microsecond=0)
    three_days_ago = now - timedelta(days=3)

    # Handle POST request for assigning or unassigning tickets or scheduled events
    if request.method == 'POST':
        ticket_id = request.form.get('ticket_id')
        event_id = request.form.get('event_id')
        it_executive = request.form.get('it_executive')  # Get the selected IT executive
        action = request.form.get('action')  # Assign or Remove

        if not it_executive:
            flash("No IT executive selected.")
            return redirect(url_for('admin_tasks'))

        try:
            if ticket_id:
                ticket_ref = db.collection('tickets').document(ticket_id)
                ticket_data = ticket_ref.get().to_dict()
                
                if ticket_data is None:
                    flash("Ticket not found.")
                    return redirect(url_for('admin_tasks'))

                history = ticket_data.get('history', [])  # Fetch history or create an empty list
                timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

                if action == "remove":
                    # Remove IT executive from the ticket
                    ticket_ref.update({
                        'assigned_to': firestore.ArrayRemove([it_executive])
                    })
                    # Check if the ticket has no more assigned executives, set status to "Open"
                    updated_ticket = ticket_ref.get().to_dict()
                    if not updated_ticket.get('assigned_to'):
                        ticket_ref.update({'status': 'Open'})

                    # Log history update
                    history.append({
                        'note': f"{it_executive} was removed from the ticket.",
                        'status': updated_ticket.get('status', 'Open'),
                        'timestamp': timestamp_str
                    })
                    ticket_ref.update({'history': history})
                    flash(f"{it_executive} removed from the ticket.")

                elif action == "assign":
                    # Assign IT executive to the ticket
                    ticket_ref.update({
                        'assigned_to': firestore.ArrayUnion([it_executive]),
                        'status': 'In Progress'
                    })

                    # Log history update
                    history.append({
                        'note': f"{it_executive} was assigned to the ticket.",
                        'status': 'In Progress',
                        'timestamp': timestamp_str
                    })
                    ticket_ref.update({'history': history})
                    flash(f"Ticket assigned to {it_executive}.")

            elif event_id:
                event_ref = db.collection('scheduled_events').document(event_id)
                event_data = event_ref.get().to_dict()

                if event_data is None:
                    flash("Scheduled event not found.")
                    return redirect(url_for('admin_tasks'))

                history = event_data.get('history', [])
                timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

                if action == "remove":
                    event_ref.update({
                        'assigned_to': firestore.ArrayRemove([it_executive])
                    })
                    history.append({
                        'note': f"{it_executive} was removed from the event.",
                        'timestamp': timestamp_str
                    })
                    event_ref.update({'history': history})
                    flash(f"{it_executive} removed from the scheduled event.")

                elif action == "assign":
                    event_ref.update({
                        'assigned_to': firestore.ArrayUnion([it_executive])
                    })
                    history.append({
                        'note': f"{it_executive} was assigned to the event.",
                        'timestamp': timestamp_str
                    })
                    event_ref.update({'history': history})
                    flash(f"Scheduled event assigned to {it_executive}.")

        except Exception as e:
            flash(f"An error occurred while updating: {str(e)}")

        return redirect(url_for('admin_tasks'))

    # Fetch all tickets
    tickets_ref = db.collection('tickets').stream()
    tickets = []
    for ticket in tickets_ref:
        ticket_data = ticket.to_dict()
        ticket_data['id'] = ticket.id
        ticket_data['created_at'] = ticket_data.get('created_at', None)  # Handle missing created_at
        tickets.append(ticket_data)

    # Fetch all IT executives
    it_executives_ref = db.collection('it_executives').stream()
    it_executives = [{'id': it_exec.id, 'name': it_exec.get('name'), 'email': it_exec.get('email')} for it_exec in it_executives_ref]

    # Update statistics for IT executives
    for ticket in tickets:
        assigned_to = ticket.get('assigned_to', [])

        # Ensure assigned_to is always a list
        if not isinstance(assigned_to, list):
            assigned_to = [assigned_to] if isinstance(assigned_to, str) else []

        assigned_time = ticket.get('created_at')

        # Convert Firestore timestamp to datetime
        if isinstance(assigned_time, dict) and 'seconds' in assigned_time:
            assigned_time = datetime.utcfromtimestamp(assigned_time['seconds'])

        # Ensure assigned_time is a valid datetime before processing
        if isinstance(assigned_time, datetime):
            for exec in it_executives:
                if exec.get('email') and exec['email'] in assigned_to:
                    if start_of_today <= assigned_time <= end_of_today:
                        exec.setdefault('tickets_today', 0)
                        exec['tickets_today'] += 1
                    elif assigned_time < three_days_ago:
                        exec.setdefault('backlog_count', 0)
                        exec['backlog_count'] += 1

    # Fetch all scheduled events
    scheduled_events_ref = db.collection('scheduled_events').stream()
    scheduled_events = [{'id': event.id, **event.to_dict()} for event in scheduled_events_ref]

    return render_template('admin_tasks.html', tickets=tickets, it_executives=it_executives, scheduled_events=scheduled_events, now=now)


from google.cloud.firestore_v1 import _helpers

@app.route('/ticket_history', methods=['GET'])
def ticket_history():
    if 'user_token' not in session:
        flash("Please log in to view the ticket history.")
        return redirect(url_for('login_page'))

    user_email = session.get('user_email')
    if not user_email:
        flash("User email not found in session.")
        return redirect(url_for('login_page'))

    # Determine user role
    user_role = 'user'  # Default role for normal users
    if session.get('is_admin'):
        user_role = 'admin'
    elif session.get('is_it_executive'):
        user_role = 'it_executive'

    print(f"User email: {user_email}, Role: {user_role}")  # Debug logging

    tickets = []

    try:
        if user_role == 'admin':
            tickets_ref = db.collection('tickets').stream()
        elif user_role == 'it_executive':
            assigned_tickets_ref = db.collection('tickets').where('assigned_to', 'array_contains', user_email).stream()
            open_tickets_ref = db.collection('tickets').where('status', '==', 'Open').stream()
            tickets_ref = list(assigned_tickets_ref) + list(open_tickets_ref)
        else:
            tickets_ref = db.collection('tickets').where('user_email', '==', user_email).stream()

        for ticket in tickets_ref:
            ticket_data = ticket.to_dict()
            ticket_data['id'] = ticket.id
            
            # Handle DatetimeWithNanoseconds conversion
            created_at = ticket_data.get('created_at')
            if created_at and isinstance(created_at, _helpers.DatetimeWithNanoseconds):
                ticket_data['created_at'] = created_at.replace(tzinfo=None)
            else:
                ticket_data['created_at'] = None

            ticket_data['status'] = ticket_data.get('status', 'Unknown')
            ticket_data['assigned_to'] = ticket_data.get('assigned_to', [])
            ticket_data['assigned_to_display'] = ', '.join(ticket_data['assigned_to']) if ticket_data['assigned_to'] else 'Unassigned'

            tickets.append(ticket_data)

    except Exception as e:
        print(f"Error fetching tickets for {user_role}: {str(e)}")
        flash("Error fetching tickets. Please try again.")
        return redirect(url_for('dashboard'))

    for ticket in tickets:
        print(f"Ticket ID: {ticket['id']}, Assigned To: {ticket['assigned_to_display']}, Status: {ticket['status']}")

    return render_template('ticket_history.html', tickets=tickets, user_role=user_role)




@app.route('/get_profile_info')
def get_profile_info():
    email = request.args.get('email')

    if not email:
        return jsonify({'success': False, 'message': 'No email provided.'}), 400
    
    # Fetch the profile from the 'profiles' collection in Firestore
    profile_ref = db.collection('profiles').document(email).get()
    profile_data = profile_ref.to_dict()

    if profile_data:
        return jsonify({'success': True, 'profile': profile_data})
    else:
        return jsonify({'success': False, 'message': 'Profile not found.'}), 404


@app.route('/confirm_resolved_ticket/<ticket_id>', methods=['POST'])
def confirm_resolved_ticket(ticket_id):
    if 'user_token' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    response = request.json.get('response')
    user_email = session.get('user_email')
    is_admin = session.get('is_admin', False)

    try:
        ticket_ref = db.collection('tickets').document(ticket_id)
        ticket = ticket_ref.get().to_dict()

        # Allow admins to update the ticket, or check if the user created the ticket
        if ticket and (ticket.get('user_email') == user_email or is_admin) and ticket.get('status').lower() == 'resolved':
            # If user confirms "Yes", change status to "Completed"
            if response == 'yes':
                ticket_ref.update({
                    'status': 'Completed',
                    'history': firestore.ArrayUnion([{
                        'status': 'Completed',
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'note': 'Ticket marked as completed.'
                    }])
                })

            # If user says "No", change status back to "In Progress"
            elif response == 'no':
                ticket_ref.update({
                    'status': 'In Progress',
                    'history': firestore.ArrayUnion([{
                        'status': 'In Progress',
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'note': 'User rejected the resolution, ticket reassigned.'
                    }])
                })

            return jsonify({"success": True, "message": "Ticket status updated."})
        else:
            return jsonify({"success": False, "message": "Invalid ticket or unauthorized action."}), 403

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# Route for generating reports and analytics
@app.route('/reports')
def reports():
    if 'user_token' not in session or not session.get('is_admin'):
        flash("You must be an admin to access this page.", 'error')
        return redirect(url_for('login_page'))
    return render_template('generate_report.html')

@app.route('/users', methods=['GET'])
def get_users():
    """Fetch unique assigned users from Firestore."""
    tickets_ref = db.collection('tickets')
    tickets = tickets_ref.stream()

    assigned_users = set()  # Using a set to avoid duplicates

    for ticket in tickets:
        data = ticket.to_dict()
        assigned_to = data.get('assigned_to', [])
        
        if isinstance(assigned_to, list):  # Ensure assigned_to is a list
            assigned_users.update(assigned_to)

    return jsonify(sorted(assigned_users))  # Sort users alphabetically for UI

@app.route('/report', methods=['GET'])
def get_report():
    """Fetch ticket data from Firestore, filter by assigned person, month, and date range, and return stats."""
    assigned_filter = request.args.get('assigned', 'all')
    month_filter = request.args.get('month', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Convert start_date & end_date from string to datetime
    start_date = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end_date = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    tickets_ref = db.collection('tickets')
    tickets = tickets_ref.stream()

    status_counts = {}
    priority_counts = {}
    monthly_counts = {}
    assigned_counts = {}
    user_status_counts = {}  # Stores status-wise ticket count per user
    product_counts = {}  # NEW: Track number of tickets per product

    filtered_tickets = []

    for ticket in tickets:
        data = ticket.to_dict()
        assigned_to = data.get('assigned_to', [])
        created_at = data.get('created_at')
        product = data.get('product', 'Unknown')  # Get product name

        # Convert Firestore timestamp to datetime
        if isinstance(created_at, dict) and 'seconds' in created_at:
            created_at = datetime.utcfromtimestamp(created_at['seconds'])
        elif not isinstance(created_at, datetime):
            continue

        created_at = created_at.replace(tzinfo=None)  # Ensure naive datetime for comparison
        created_month = created_at.strftime("%m")

        # Apply filters
        if (assigned_filter == "all" or assigned_filter in assigned_to) and \
           (month_filter == "all" or created_month == month_filter) and \
           (start_date is None or created_at >= start_date) and \
           (end_date is None or created_at <= end_date):

            # Count statuses
            status = data.get('status', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

            # Count priorities
            priority = data.get('priority', 'Unknown')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

            # Count monthly occurrences
            monthly_counts[created_month] = monthly_counts.get(created_month, 0) + 1

            # Count assigned persons
            for person in assigned_to:
                assigned_counts[person] = assigned_counts.get(person, 0) + 1

                # Track ticket statuses for each assigned person
                if person not in user_status_counts:
                    user_status_counts[person] = {"Open": 0, "Completed": 0, "Pending": 0}

                user_status_counts[person][status] = user_status_counts[person].get(status, 0) + 1

            # Count tickets by product
            product_counts[product] = product_counts.get(product, 0) + 1  # NEW

            filtered_tickets.append(data)

    return jsonify({
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "monthly_counts": monthly_counts,
        "assigned_counts": assigned_counts,
        "user_status_counts": user_status_counts,
        "product_counts": product_counts  # NEW: Include in response
    })


@app.route('/download', methods=['GET'])
def download_csv():
    """Generate and serve a filtered CSV report."""
    assigned_filter = request.args.get('assigned', 'all')
    month_filter = request.args.get('month', 'all')

    tickets_ref = db.collection('tickets')
    tickets = tickets_ref.stream()

    csv_file = "report.csv"
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Title", "Status", "Assigned To", "Created At", "Priority", "Product", "Room", "Description"])

        for ticket in tickets:
            data = ticket.to_dict()
            assigned_to = data.get('assigned_to', [])
            created_at = data.get('created_at')

            # Convert Firestore timestamp to datetime
            if isinstance(created_at, dict) and 'seconds' in created_at:
                created_at = datetime.utcfromtimestamp(created_at['seconds'])
            elif not isinstance(created_at, datetime):
                continue

            created_month = created_at.strftime("%m")

            # Apply filters
            if (assigned_filter == "all" or assigned_filter in assigned_to) and \
               (month_filter == "all" or created_month == month_filter):

                writer.writerow([
                    data.get("title", ""),
                    data.get("status", ""),
                    ", ".join(assigned_to),
                    created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    data.get("priority", ""),
                    data.get("product", ""),
                    data.get("room", ""),
                    data.get("description", ""),
                ])

    return send_file(
        csv_file,
        as_attachment=True,
        download_name="report.csv",
        mimetype="text/csv"
    )
@app.route('/logout')
def logout():
    session.pop('user_token', None)
    session.pop('user_email', None)
    return redirect(url_for('homepage'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8001)))

