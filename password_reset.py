# password_reset.py

from flask import Blueprint, render_template, request, session, redirect, url_for
from datetime import datetime, timedelta
import secrets
import smtplib
from email.mime.text import MIMEText
import mysql.connector
from werkzeug.security import generate_password_hash

# Create a Blueprint
password_reset_bp = Blueprint('password_reset_bp', __name__)

def get_db_connection():
    """Connect to MySQL database. Adjust credentials as needed."""
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",   # change if needed
        database="flaskdb"
    )

@password_reset_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']

        # Check if user exists
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            user_id = user['user_id']
            token = secrets.token_urlsafe(32)  # generate a secure, random token
            expiration = datetime.now() + timedelta(hours=1)  # token valid for 1 hour

            # Insert token into DB
            cursor.execute("""
                INSERT INTO password_reset_tokens (user_id, token, expiration)
                VALUES (%s, %s, %s)
            """, (user_id, token, expiration))
            db.commit()

            # Build reset link
            # e.g. http://127.0.0.1:5000/reset_password/<token>
            reset_link = request.url_root[:-1] + url_for('password_reset_bp.reset_password', token=token)
            
            # Send email
            send_reset_email(email, reset_link)

        cursor.close()
        db.close()

        # Return a generic message (for security, do not confirm if email is valid)
        return "If an account with that email exists, a password reset link was sent to the email."

    return render_template('forgot_password.html')


@password_reset_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            return "Passwords do not match!"

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT user_id, expiration 
            FROM password_reset_tokens
            WHERE token = %s
        """, (token,))
        row = cursor.fetchone()

        if not row:
            cursor.close()
            db.close()
            return "Invalid or expired token."

        # Check expiration
        if datetime.now() > row['expiration']:
            # Token expired, delete it
            cursor.execute("DELETE FROM password_reset_tokens WHERE token = %s", (token,))
            db.commit()
            cursor.close()
            db.close()
            return "This token has expired. Please request a new reset link."

        # If token is valid, update user password
        user_id = row['user_id']
        hashed_pw = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password = %s WHERE user_id = %s", (hashed_pw, user_id))
        db.commit()

        # Delete token once used
        cursor.execute("DELETE FROM password_reset_tokens WHERE token = %s", (token,))
        db.commit()

        cursor.close()
        db.close()

        return "Your password has been reset successfully. <a href='/login'>Login</a>"

    else:
        # GET method, show the reset form if token is valid (and not expired)
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT user_id, expiration 
            FROM password_reset_tokens
            WHERE token = %s
        """, (token,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        if not row or datetime.now() > row['expiration']:
            return "Invalid or expired token."

        # Render the form
        return render_template('reset_password.html', token=token)


def send_reset_email(to_email, reset_link):
    """
    send_reset_email(to_email, reset_link)
    A basic example using Python's smtplib library.

    For production, it's recommended to use a more robust solution 
    like Flask-Mail or an external service (SendGrid, Mailgun, etc.).
    """
    # Replace with your SMTP settings
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT   = 587
    SMTP_USER   = 'kingsmansoftwaresolution@gmail.com'
    SMTP_PASS   = 'hhsy drzs yajh csej'  # or an app-specific password

    subject = "Password Reset Request"
    body = f"""
    You requested a password reset. 
    Click the link below to reset your password:
    {reset_link}
    
    If you did not request a password reset, you can ignore this email.
    """

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = to_email

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print("Reset email sent successfully.")
    except Exception as e:
        print("Failed to send email:", e)
