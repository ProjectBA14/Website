from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import firebase_admin
from firebase_admin import credentials, auth, storage, firestore
from werkzeug.utils import secure_filename
import os
import secrets
import requests
from firebase_admin.exceptions import FirebaseError  # Use FirebaseError for exceptions
from datetime import datetime,timedelta,timezone
import json

# OAuth libraries
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
from google.auth.exceptions import RefreshError


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
GOOGLE_CLIENT_ID = "682740205264-l0bcvo8a6ht8rh0mo8gc8u1b6lrtu4jn.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"

flow = Flow.from_client_config(
    {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "project_id": "windy-elevator-437515-p4",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": ['https://localhost:8001/callback', 'https://ticketing-57ep.onrender.com/callback'],
        }
    },
    scopes=['https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email', 'openid'],
    redirect_uri=redirect_uri
)

# Configurations for file uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Determine the redirect URI based on the environment
if os.getenv('FLASK_ENV') == 'development':
    redirect_uri = 'https://localhost:8001/callback'
else:
    redirect_uri = 'https://ticketing-57ep.onrender.com/callback'
# Helper function to check if the uploaded file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
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

@app.route('/', methods=['GET', 'POST'])
def homepage():
    return redirect('login')


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
            response = requests.post(f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={'AIzaSyCEUHsjOvi_5AbRgHSTRE0Tgk6QDcFhCoM'}",
                                     data=json.dumps(payload),
                                     headers={"Content-Type": "application/json"})
            response_data = response.json()

            if 'idToken' not in response_data:
                flash("Invalid email or password.", 'error')
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
# Google login route
@app.route('/google_login')
def google_login():
    # Set the redirect_uri dynamically
    flow.redirect_uri = redirect_uri
    authorization_url, state = flow.authorization_url()
    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session['state'] == request.args['state']:
        flash("Invalid state parameter.")
        return redirect(url_for('login_page'))

    credentials = flow.credentials
    request_session = google.auth.transport.requests.Request()
    id_info = id_token.verify_oauth2_token(
        id_token=credentials.id_token, request=request_session, audience=GOOGLE_CLIENT_ID
    )

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
        flash("You must use an email from the gdgu.org domain.")
        return redirect(url_for('login_page'))


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
                            'note': progress_note if status == 'In Progress' else None
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
        it_executives = request.form.getlist('it_executive')  # Get the list of selected IT executives

        # Ensure at least one IT executive is selected
        if not it_executives:
            flash("No IT executive(s) selected.")
            return redirect(url_for('admin_tasks'))

        try:
            # Update the ticket if the assignment is for a ticket
            if ticket_id:
                ticket_ref = db.collection('tickets').document(ticket_id)
                if "unassign" in it_executives:
                    # Unassign the specified IT executives from the ticket
                    for exec_email in it_executives:
                        ticket_ref.update({
                            'assigned_to': firestore.ArrayRemove([exec_email])
                        })
                    # Check if the ticket has no more assigned executives, set status to "Open"
                    ticket = ticket_ref.get().to_dict()
                    if not ticket.get('assigned_to'):
                        ticket_ref.update({'status': 'Open'})
                    flash("Selected IT executive(s) unassigned from the ticket.")
                else:
                    # Assign the specified IT executives to the ticket
                    ticket_ref.update({
                        'assigned_to': firestore.ArrayUnion(it_executives),
                        'status': 'in-progress'
                    })
                    flash("Ticket successfully assigned to selected IT executive(s).")
            
            # Update the scheduled event if the assignment is for an event
            elif event_id:
                event_ref = db.collection('scheduled_events').document(event_id)
                if "unassign" in it_executives:
                    # Unassign the specified IT executives from the event
                    for exec_email in it_executives:
                        event_ref.update({
                            'assigned_to': firestore.ArrayRemove([exec_email])
                        })
                    flash("Selected IT executive(s) unassigned from the scheduled event.")
                else:
                    # Assign the specified IT executives to the event
                    event_ref.update({
                        'assigned_to': firestore.ArrayUnion(it_executives)
                    })
                    flash("Scheduled event successfully assigned to selected IT executive(s).")

        except Exception as e:
            flash(f"An error occurred while updating: {str(e)}")

        return redirect(url_for('admin_tasks'))

    # Fetch all tickets
    tickets_ref = db.collection('tickets').stream()
    tickets = [{'id': ticket.id, **ticket.to_dict()} for ticket in tickets_ref]

    # Fetch all IT executives
    it_executives_ref = db.collection('it_executives').stream()
    it_executives = [{'id': it_exec.id, 'name': it_exec.get('name'), 'email': it_exec.get('email')} for it_exec in it_executives_ref]

    # Update statistics for IT executives
    for ticket in tickets:
        assigned_to = ticket.get('assigned_to')
        if assigned_to and isinstance(assigned_to, list):
            assigned_time = ticket.get('created_at')
            if assigned_time:
                for exec in it_executives:
                    if exec['email'] in assigned_to:
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

    # Debug logging for role
    print(f"User email: {user_email}, Role: {user_role}")

    tickets = []

    # Fetch tickets based on the user role
    try:
        if user_role == 'admin':
            # Admin can see all tickets
            tickets_ref = db.collection('tickets').stream()
            tickets = [{'id': ticket.id, **ticket.to_dict()} for ticket in tickets_ref]
        elif user_role == 'it_executive':
            # IT Executives can see assigned tickets and open tickets
            assigned_tickets_ref = db.collection('tickets').where('assigned_to', 'array_contains', user_email).stream()
            open_tickets_ref = db.collection('tickets').where('status', '==', 'Open').stream()
            tickets = [{'id': ticket.id, **ticket.to_dict()} for ticket in assigned_tickets_ref]
            tickets += [{'id': ticket.id, **ticket.to_dict()} for ticket in open_tickets_ref]
        else:
            # Regular users can only see their own tickets (open, assigned, and resolved)
            tickets_ref = db.collection('tickets').where('user_email', '==', user_email).stream()
            tickets = [{'id': ticket.id, **ticket.to_dict()} for ticket in tickets_ref]
    except Exception as e:
        # Log the error for debugging
        print(f"Error fetching tickets for {user_role}: {str(e)}")
        flash("Error fetching tickets. Please try again.")
        return redirect(url_for('dashboard'))

    # Handle both string and array cases for assigned_to
    for ticket in tickets:
        assigned_to = ticket.get('assigned_to')
        if isinstance(assigned_to, list):
            ticket['assigned_to_display'] = ', '.join(assigned_to)
        elif isinstance(assigned_to, str):
            ticket['assigned_to_display'] = assigned_to
        else:
            ticket['assigned_to_display'] = 'Unassigned'

        # Debugging the ticket data
        print(f"Ticket ID: {ticket['id']}, Assigned To: {ticket['assigned_to_display']}, Status: {ticket['status']}")

    # Render the template with the fetched tickets
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



@app.route('/logout')
def logout():
    session.pop('user_token', None)
    session.pop('user_email', None)
    return redirect(url_for('homepage'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

