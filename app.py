from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from functools import wraps
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(24)  # Securely generated secret key

def connect_to_database():
    conn_params = {
        'host': 'financial-dashboard-4996.7s5.aws-ap-south-1.cockroachlabs.cloud',
        'port': 26257,
        'user': 'satvik',
        'password': 'RWU4tpbY_rQDSuaY7O3jEQ',
        'database': 'defaultdb',
        'sslmode': 'verify-full',
        'sslrootcert': 'root.crt' # Replace with the correct path
    }

    conn_str = "host={host} port={port} user={user} password={password} dbname={database} sslmode={sslmode} sslrootcert={sslrootcert}".format(**conn_params)
    #postgresql://web-weavers:<ENTER-SQL-USER-PASSWORD>@web-weavers-4063.7s5.aws-ap-south-1.cockroachlabs.cloud:26257/ISS_users?sslmode=verify-full
    # Connect to the database
    try:
        conn = psycopg2.connect(conn_str)
        return conn
    except psycopg2.OperationalError as e:
        return None
# Database connection setup
con = connect_to_database()
cur = con.cursor()

def create_table():
    create_table_query = """
    CREATE TABLE IF NOT EXISTS UserDetails (
        UserId SERIAL PRIMARY KEY,
        UserName VARCHAR(255) NOT NULL UNIQUE,
        UserEmail VARCHAR(255) UNIQUE,
        UserPassword VARCHAR(255) NOT NULL
    );
    """
    cur.execute(create_table_query)
    con.commit()

create_table()

# Define a decorator to require authentication
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

# Function to write users to the database
def write_user(username, email, password):
    try:
        cur.execute("INSERT INTO UserDetails (UserName, UserEmail, UserPassword) VALUES (%s, %s, %s);", (username, email, password))
        con.commit()
        print("User added successfully")
    except Exception as e:
        print("Error adding user:", e)

# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        cur.execute("SELECT * FROM UserDetails WHERE UserName = %s", (username,))
        user = cur.fetchone()
        if user:
            return "User already exists. Please login."
        email = request.form['email']
        password = request.form['password']
        write_user(username, email, password)
        return redirect(url_for('login'))
    return render_template('signup.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cur.execute("SELECT * FROM UserDetails WHERE UserName=%s", (username,))
        user = cur.fetchone()
        if user:
            if password == user[3]:
                session['username'] = username
                session['user_id'] = user[0]
                return redirect(url_for('home', username=username))
            return "Invalid Username or Password. Please Try Again."
        return "User doesn't Exist. Please Signup."

    if 'username' in session:
        return redirect(url_for('home', username=session['username']))

    return render_template('login.html')

@app.route('/home/<username>')
@login_required
def home(username):
    return f"Welcome, {username}!"

if __name__ == '__main__':
    app.run(debug=True)

cur.close()
con.close()
