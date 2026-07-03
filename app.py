from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "waste_management_secret_key"

# MySQL Config (Aiven)
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 3306))

mysql = MySQL(app)

# ---------------- HOME ----------------
@app.route('/')
def home():

    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM WASTE_COLLECTION")
    total_requests = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM WASTE_COLLECTION WHERE STATUS='APPROVED'")
    approved_requests = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM USERS")
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
        INSERT INTO USERS(NAME, EMAIL, PASSWORD)
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
        FROM USERS
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


# ---------------- USER DASHBOARD ----------------
@app.route('/user_dashboard')
def user_dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT COLLECTION_ID, WASTE_TYPE, LOCATION, COLLECTION_DATE, STATUS
    FROM WASTE_COLLECTION
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
           WC.STATUS
    FROM WASTE_COLLECTION WC
    JOIN USERS U ON WC.USER_ID = U.USER_ID
    """)
    requests = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM WASTE_COLLECTION")
    total = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM WASTE_COLLECTION WHERE STATUS='PENDING'")
    pending = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM WASTE_COLLECTION WHERE STATUS='APPROVED'")
    approved = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM WASTE_COLLECTION WHERE STATUS='REJECTED'")
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

        cur = mysql.connection.cursor()

        cur.execute("""
        INSERT INTO WASTE_COLLECTION
        (USER_ID, WASTE_TYPE, LOCATION, COLLECTION_DATE, STATUS)
        VALUES (%s, %s, %s, %s, 'PENDING')
        """, (user_id, waste_type, location, collection_date))

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
    UPDATE WASTE_COLLECTION
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
    UPDATE WASTE_COLLECTION
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
    DELETE FROM WASTE_COLLECTION
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