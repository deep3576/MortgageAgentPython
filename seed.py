# seed.py
import mysql.connector
from werkzeug.security import generate_password_hash

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",           # change if needed
    #database="flaskdb"     # your database name
)

mycursor = mydb.cursor()

# Create table if not exists

mycursor.execute("""CREATE DATABASE IF NOT EXISTS flaskdb;""")
mycursor.execute("""USE flaskdb;""")





mycursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
                 first_name VARCHAR(100) NULL,
                 last_name VARCHAR(100) NULL,
                 phone VARCHAR(20) NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL
)
""")
# Create admin user if it doesn't exist

mycursor.execute("""CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(255) NOT NULL,
    expiration DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);""")

mycursor.execute("""CREATE TABLE IF NOT EXISTS admin_assignment (
    id INT AUTO_INCREMENT PRIMARY KEY,
    last_assigned_admin_id INT NOT NULL,
    FOREIGN KEY (last_assigned_admin_id) REFERENCES users(user_id)
);
""")



mycursor.execute("""CREATE TABLE IF NOT EXISTS applications (
    application_id INT AUTO_INCREMENT PRIMARY KEY,
    broker_id INT NOT NULL,
    admin_assigned_id INT DEFAULT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Pending',
    pay_stubs VARCHAR(255) DEFAULT NULL,
    bank_statements VARCHAR(255) DEFAULT NULL,
    credit_report VARCHAR(255) DEFAULT NULL,
    sale_agreement VARCHAR(255) DEFAULT NULL,
    gift_letter VARCHAR(255) DEFAULT NULL,
    property_info VARCHAR(255) DEFAULT NULL,
    FOREIGN KEY (broker_id) REFERENCES users(user_id),
    FOREIGN KEY (admin_assigned_id) REFERENCES users(user_id)
);
""")

mycursor.execute("""CREATE TABLE IF NOT EXISTS application_documents (
    doc_id INT AUTO_INCREMENT PRIMARY KEY,
    application_id INT NOT NULL,
    doc_type VARCHAR(100) NOT NULL,
    doc_path VARCHAR(255),
    doc_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    FOREIGN KEY (application_id) REFERENCES applications(application_id)
);
""")
admin_email = 'admin@company.com'
admin_plain_password = 'admin123'
admin_role = 'admin'

# Hash the admin password before saving
admin_hashed_pw = generate_password_hash(admin_plain_password)

mycursor.execute("SELECT * FROM users WHERE email = %s", (admin_email,))
row = mycursor.fetchone()

if not row:
    mycursor.execute(
        "INSERT INTO users (email, password, role) VALUES (%s, %s, %s)",
        (admin_email, admin_hashed_pw, admin_role)
    )
    mydb.commit()
    print(f"Admin user ({admin_email}) created.")
else:
    print("Admin user already exists.")

mycursor.close()
mydb.close()
