# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import smtplib
from email.mime.text import MIMEText
from  password_reset import password_reset_bp
app = Flask(__name__)
app.secret_key = 'replace_with_a_random_secret_key'
app.register_blueprint(password_reset_bp)

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



# Configure MySQL Connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",      # change if needed
        database="flaskdb"
    )



@app.route('/')
def home():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form['phone']
        email = request.form['email']
        password = request.form['password']
        # Always hash the password
        hashed_pw = generate_password_hash(password)

        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if the email already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            db.close()
            return "Email already registered. Please log in instead."

        # Otherwise, insert user with role=broker
        insert_query = """
            INSERT INTO users (first_name, last_name, phone, email, password, role)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (first_name, last_name, phone, email, hashed_pw, 'broker'))
        db.commit()

        cursor.close()
        db.close()

        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user['password'], password):
            # Store user info in session
            session['user_id'] = user['user_id']
            session['email'] = user['email']
            session['role'] = user['role']

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('broker_dashboard'))
        else:
            return "Invalid credentials, please try again."

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/admin')
def admin_dashboard():
    # Ensure only admin can view this page
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('home'))
    return render_template('admin.html', subpage='applications')
# ---------------------------------------------
# 1) New Application Route (Broker)
# ---------------------------------------------
@app.route('/broker/new_application', methods=['GET', 'POST'])
def new_application():
    # Ensure only broker
    if 'role' not in session or session['role'] != 'broker':
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        # Handle form + optional uploads
        broker_id = session['user_id']
        
        pay_stubs_file = request.files.get('pay_stubs')
        bank_statements_file = request.files.get('bank_statements')
        credit_report_file = request.files.get('credit_report')
        sale_agreement_file = request.files.get('sale_agreement')
        gift_letter_file = request.files.get('gift_letter')
        property_info_file = request.files.get('property_info')

        # Save files if provided
        pay_stubs_path = save_file(pay_stubs_file) if pay_stubs_file and allowed_file(pay_stubs_file.filename) else None
        bank_statements_path = save_file(bank_statements_file) if bank_statements_file and allowed_file(bank_statements_file.filename) else None
        credit_report_path = save_file(credit_report_file) if credit_report_file and allowed_file(credit_report_file.filename) else None
        sale_agreement_path = save_file(sale_agreement_file) if sale_agreement_file and allowed_file(sale_agreement_file.filename) else None
        gift_letter_path = save_file(gift_letter_file) if gift_letter_file and allowed_file(gift_letter_file.filename) else None
        property_info_path = save_file(property_info_file) if property_info_file and allowed_file(property_info_file.filename) else None

        # Assign admin via round-robin
        admin_id = round_robin_assign_admin()

        # Insert into DB
        db = get_db_connection()
        cursor = db.cursor()
        insert_query = """
            INSERT INTO applications (
                broker_id, 
                admin_assigned_id,
                status,
                pay_stubs,
                bank_statements,
                credit_report,
                sale_agreement,
                gift_letter,
                property_info
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (
            broker_id,
            admin_id,
            'Pending',  # default status
            pay_stubs_path,
            bank_statements_path,
            credit_report_path,
            sale_agreement_path,
            gift_letter_path,
            property_info_path
        ))
        db.commit()
        cursor.close()
        db.close()

        return redirect(url_for('broker_applications'))
    
    # GET request: show the new application form
    return render_template('new_application.html')

def save_file(file_obj):
    """Save an uploaded file to the uploads folder, returning the relative path."""
    filename = secure_filename(file_obj.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file_obj.save(file_path)
    # store in DB as 'uploads/filename'
    return f"uploads/{filename}"

# ---------------------------------------------
# 2) Broker: View Applications
# ---------------------------------------------

# Utility to check file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -----------
# Round Robin
# -----------
# For demonstration, we'll keep the 'index' in a global variable. 
# In production, store it in a DB or config for persistence.
round_robin_index = 0

def round_robin_assign_admin():
    global round_robin_index
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    # Get all admin users
    cursor.execute("SELECT user_id FROM users WHERE role = 'admin'")
    admins = cursor.fetchall()
    
    if not admins:
        # If no admin, return None or handle error
        cursor.close()
        db.close()
        return None
    
    # Assign the admin based on the round_robin_index
    admin_id = admins[round_robin_index]['user_id']
    
    # Increment the index
    round_robin_index = (round_robin_index + 1) % len(admins)
    
    cursor.close()
    db.close()
    
    return admin_id

@app.route('/admin/applications')
def admin_applications():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('home'))

    admin_id = session['user_id']
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.application_id, a.broker_id, a.status, u.email as broker_email
        FROM applications a
        JOIN users u ON a.broker_id = u.user_id
        WHERE a.admin_assigned_id = %s
        ORDER BY a.application_id DESC
    """, (admin_id,))
    assigned_apps = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template(
        'admin.html',
        subpage='applications',      # <--- we pass 'applications'
        applications=assigned_apps
    )


@app.route('/admin/application/<int:app_id>', methods=['GET', 'POST'])
def admin_application_details(app_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('home'))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # Get application details
    cursor.execute("""
        SELECT a.*, b.email AS broker_email
        FROM applications a
        JOIN users b ON a.broker_id = b.user_id
        WHERE a.application_id = %s
    """, (app_id,))
    application = cursor.fetchone()

    if not application:
        cursor.close()
        db.close()
        return "Application not found."

    if request.method == 'POST':
        # ... handle form actions (update status, approve docs, request more docs, etc.) ...
        pass

    # Query documents
    cursor.execute("""
        SELECT * FROM application_documents
        WHERE application_id = %s
    """, (app_id,))
    docs = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        'admin.html', 
        subpage='application_details',   # <--- we pass 'application_details'
        application=application,
        docs=docs
    )
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('home'))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # Get application details
    cursor.execute("""
        SELECT a.*, b.email AS broker_email
        FROM applications a
        JOIN users b ON a.broker_id = b.user_id
        WHERE a.application_id = %s
    """, (app_id,))
    application = cursor.fetchone()

    if not application:
        cursor.close()
        db.close()
        return "Application not found."

    if request.method == 'POST':
        # ... handle form actions (update status, approve docs, request more docs, etc.) ...
        pass

    # Query documents
    cursor.execute("""
        SELECT * FROM application_documents
        WHERE application_id = %s
    """, (app_id,))
    docs = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        'admin.html', 
        subpage='application_details',   # <--- we pass 'application_details'
        application=application,
        docs=docs
    )
# -----------------------------------------------------------------
# BROKER re-upload route for rejected or pending docs, for example
# -----------------------------------------------------------------
@app.route('/broker')
def broker_dashboard():
    if 'role' not in session or session['role'] != 'broker':
        return redirect(url_for('home'))

    return render_template(
        'broker.html',
        subpage='dashboard'   # <--- 'dashboard'
    )

@app.route('/broker/applications')
def broker_applications():
    if 'role' not in session or session['role'] != 'broker':
        return redirect(url_for('home'))

    broker_id = session['user_id']
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT application_id, admin_assigned_id, status 
        FROM applications
        WHERE broker_id = %s
        ORDER BY application_id DESC
    """, (broker_id,))
    apps = cursor.fetchall()
    cursor.close()
    db.close()
    
    return render_template(
        'broker.html',
        subpage='broker_applications',  # <--- 'broker_applications'
        applications=apps
    )

@app.route('/broker/application/<int:app_id>/edit', methods=['GET', 'POST'])
def edit_application(app_id):
    if 'role' not in session or session['role'] != 'broker':
        return redirect(url_for('home'))

    if request.method == 'POST':
        # handle re-uploads or updates
        pass
    else:
        # fetch the application & docs
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM applications WHERE application_id = %s", (app_id,))
        application = cursor.fetchone()

        if not application:
            return "Application not found."

        # get docs
        cursor.execute("""
            SELECT * FROM application_documents
            WHERE application_id = %s
        """, (app_id,))
        docs = cursor.fetchall()

        cursor.close()
        db.close()

        return render_template(
            'broker.html',
            subpage='edit_application',  # <--- 'edit_application'
            application=application,
            docs=docs
        )

if __name__ == '__main__':
    app.run(debug=True)

if __name__ == '__main__':
    app.run(debug=True)
