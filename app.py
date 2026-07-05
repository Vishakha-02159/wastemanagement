import pymysql
from flask import Flask, render_template, request, redirect, session
from werkzeug.utils import secure_filename  
import os
import cloudinary
import cloudinary.uploader
from werkzeug.security import generate_password_hash, check_password_hash

pymysql.install_as_MySQLdb()

app = Flask(__name__)
app.secret_key = "waste_management_secret_key"

# DB CONFIG
import MySQLdb

app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 3306))

from flask_mysqldb import MySQL
mysql = MySQL(app)
#---------- cloudinary config -----------
cloudinary.config(
    cloud_name="lyk58rp7",
    api_key="381895628354541",
    api_secret="C_-JC5QnSzpqdhqD1gkwBS49zyc"
)

# ---------------- HOME ----------------
@app.route('/')
def home():

    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM waste_collection")
    total_requests = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM waste_collection WHERE STATUS='APPROVED'")
    approved_requests = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0] or 0

    cur.close()

    return render_template(
        'index.html',
        total_requests=total_requests,
        approved_requests=approved_requests,
        total_users=total_users
    )


# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        cur = mysql.connection.cursor()

        cur.execute("""
        INSERT INTO users(name, email, password)
        VALUES(%s, %s, %s)
        """, (name, email, hashed_password))

        mysql.connection.commit()
        cur.close()

        return redirect('/login')

    return render_template('register.html')


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()

        cur.execute("""
        SELECT USER_ID, NAME, EMAIL, PASSWORD, ROLE
        FROM users
        WHERE EMAIL=%s
        """, (email,))

        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[3], password):

            session['user_id'] = user[0]
            session['name'] = user[1]
            session['role'] = user[4].upper()

            if session['role'] == 'ADMIN':
                return redirect('/admin_dashboard')
            else:
                return redirect('/user_dashboard')

        return "Invalid Email or Password"

    return render_template('login.html')


# ---------------- CONTACT ----------------
@app.route('/contact')
def contact():
    return render_template('contact.html')

#----------------- FORGOT PASSWORD ----------------
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        session['reset_email'] = email
        return redirect('/reset_password')

    return render_template('forgot_password.html')
#----------------- RESET PASSWORD ----------------
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            return "Passwords do not match"

        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE users
            SET PASSWORD=%s
            WHERE EMAIL=%s
        """, (generate_password_hash(new_password), session['reset_email']))

        mysql.connection.commit()
        cur.close()

        return redirect('/login')

    return render_template('reset_password.html')


# ---------------- USER DASHBOARD ----------------
@app.route('/user_dashboard')
def user_dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT COLLECTION_ID, WASTE_TYPE, LOCATION, COLLECTION_DATE, STATUS
    FROM waste_collection
    WHERE USER_ID=%s
    """, (session['user_id'],))

    data = cur.fetchall()
    cur.close()

    return render_template('user_dashboard.html', data=data)


# ---------------- ADMIN DASHBOARD ----------------
@app.route('/admin_dashboard')
def admin_dashboard():

    if session.get('role', '').upper() != 'ADMIN':
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT WC.COLLECTION_ID,
           U.NAME,
           WC.WASTE_TYPE,
           WC.LOCATION,
           WC.COLLECTION_DATE,
           WC.STATUS,
           WC.IMAGE_PATH
    FROM waste_collection WC
    JOIN users U ON WC.USER_ID = U.USER_ID
    """)
    requests = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM waste_collection")
    total = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM waste_collection WHERE STATUS='PENDING'")
    pending = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM waste_collection WHERE STATUS='APPROVED'")
    approved = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM waste_collection WHERE STATUS='REJECTED'")
    rejected = cur.fetchone()[0] or 0

    cur.close()

    return render_template(
        'admin_dashboard.html',
        requests=requests,
        total=total,
        pending=pending,
        approved=approved,
        rejected=rejected
    )


# ---------------- WASTE COLLECTION ----------------
@app.route('/waste_collection', methods=['GET', 'POST'])
def waste_collection():

    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':

        user_id = session['user_id']
        waste_type = request.form['waste_type']
        location = request.form['location']
        collection_date = request.form['collection_date']

        photo = request.files['photo']

        result = cloudinary.uploader.upload(photo)

        image_url = result["secure_url"]

        cur = mysql.connection.cursor()

        cur.execute("""
        INSERT INTO waste_collection
        (USER_ID, WASTE_TYPE, LOCATION, COLLECTION_DATE, IMAGE_PATH, STATUS)
        VALUES (%s, %s, %s, %s, %s, 'PENDING')
        """, (user_id, waste_type, location, collection_date, image_url))

        mysql.connection.commit()
        cur.close()

        return redirect('/user_dashboard')

    return render_template('waste_collection.html')


# ---------------- APPROVE ----------------
@app.route('/approve/<int:id>')
def approve(id):

    if session.get('role','').upper() != 'ADMIN':
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute("""
    UPDATE waste_collection
    SET STATUS='APPROVED'
    WHERE COLLECTION_ID=%s
    """, (id,))

    mysql.connection.commit()
    cur.close()

    return redirect('/admin_dashboard')


# ---------------- REJECT ----------------
@app.route('/reject/<int:id>')
def reject(id):

    if session.get('role','').upper() != 'ADMIN':
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute("""
    UPDATE waste_collection
    SET STATUS='REJECTED'
    WHERE COLLECTION_ID=%s
    """, (id,))

    mysql.connection.commit()
    cur.close()

    return redirect('/admin_dashboard')


# ---------------- DELETE ----------------
@app.route('/delete/<int:id>')
def delete(id):

    if session.get('role','').upper() != 'ADMIN':
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute("""
    DELETE FROM waste_collection
    WHERE COLLECTION_ID=%s
    """, (id,))

    mysql.connection.commit()
    cur.close()

    return redirect('/admin_dashboard')


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


if __name__ == '__main__':
    app.run(debug=True)