from flask import Flask, render_template, request, redirect, url_for, session , jsonify
from psycopg2 import extras
import psycopg2
import datetime
from decimal import Decimal
from functools import wraps
import secrets
from datetime import datetime, timedelta
import requests
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
        'sslrootcert': 'root.crt'  # Replace with the correct path
    }

    conn_str = "host={host} port={port} user={user} password={password} dbname={database} sslmode={sslmode} sslrootcert={sslrootcert}".format(**conn_params)
    try:
        conn = psycopg2.connect(conn_str)
        return conn
    except psycopg2.OperationalError as e:
        print("Could not connect to the database:", e)
        return None

# Database connection setup
con = connect_to_database()
if con is None:
    print("Database connection failed. Exiting...")
    exit(1)
cur = con.cursor()

def create_table():
    create_user_table_query = """
    CREATE TABLE IF NOT EXISTS UserDetails (
        UserId SERIAL PRIMARY KEY,
        UserName VARCHAR(255) NOT NULL UNIQUE,
        UserEmail VARCHAR(255) UNIQUE,
        UserPassword VARCHAR(255) NOT NULL
    );
    """
    cur.execute(create_user_table_query)
    
    create_user_money_table_query = """
    CREATE TABLE IF NOT EXISTS UserMoney (
        MoneyId SERIAL PRIMARY KEY,
        UserId INTEGER REFERENCES UserDetails(UserId),
        UserIncome DECIMAL(10,2) NOT NULL,
        IncomeDate DATE NOT NULL
    );
    """
    cur.execute(create_user_money_table_query)
    
    create_user_transaction_table_query = """
    CREATE TABLE IF NOT EXISTS UserTransaction (
        TransactionId SERIAL PRIMARY KEY,
        UserId INTEGER REFERENCES UserDetails(UserId),
        Amount DECIMAL(10, 2) NOT NULL,
        Reason VARCHAR(255) NOT NULL,
        TransactionType VARCHAR(10) CHECK (TransactionType IN ('withdraw', 'deposit')) NOT NULL,
        TransactionDate DATE NOT NULL
    );
    """
    cur.execute(create_user_transaction_table_query)
    
    create_crypto_transaction_table_query = """
    CREATE TABLE IF NOT EXISTS CryptoTransaction (
        CryptoId SERIAL PRIMARY KEY,
        UserId INTEGER REFERENCES UserDetails(UserId),
        CryptoName VARCHAR(255) NOT NULL,
        CryptoAmount DECIMAL(18, 8) NOT NULL,
        TransactionType VARCHAR(10) CHECK (TransactionType IN ('bought', 'sold')) NOT NULL,
        TransactionDate DATE NOT NULL
    );
    """
    cur.execute(create_crypto_transaction_table_query)

    create_stock_transaction_table_query = """
    CREATE TABLE IF NOT EXISTS StockTransaction (
        StockId SERIAL PRIMARY KEY,
        UserId INTEGER REFERENCES UserDetails(UserId),
        StockName VARCHAR(255) NOT NULL,
        StockAmount DECIMAL(10, 2) NOT NULL,
        TransactionType VARCHAR(10) CHECK (TransactionType IN ('bought', 'sold')) NOT NULL,
        TransactionDate DATE NOT NULL
    );
    """
    cur.execute(create_stock_transaction_table_query)
    con.commit()

    create_budget_table = """
    CREATE TABLE IF NOT EXISTS Budget (
        BudgetId SERIAL PRIMARY KEY,
        UserId INTEGER REFERENCES UserDetails(UserId),
        Category VARCHAR(255) NOT NULL,
        BudgetAmount DECIMAL(10, 2) NOT NULL
    );
    """
    cur.execute(create_budget_table)
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

@app.route('/home/<username>', methods=['GET', 'POST'])
@login_required
def home(username):
    cur.execute("SELECT SUM(UserMoney.UserIncome) FROM UserDetails JOIN UserMoney ON UserDetails.UserId = UserMoney.UserId WHERE UserDetails.UserName=%s;", (username,))
    income = cur.fetchone()
    if income is None or income[0] is None:
        income = (0,)

    cur.execute("SELECT SUM(UserTransaction.Amount) AS total_amount FROM UserTransaction JOIN UserDetails ON UserDetails.UserId = UserTransaction.UserId WHERE UserDetails.UserName = %s AND UserTransaction.TransactionType='deposit'", (username,))
    balance = cur.fetchone()
    cur.execute("SELECT SUM(UserTransaction.Amount) AS total_amount FROM UserTransaction JOIN UserDetails ON UserDetails.UserId = UserTransaction.UserId WHERE UserDetails.UserName = %s AND UserTransaction.TransactionType='withdraw'", (username,))
    balance2 = cur.fetchone()
    if balance2 is None or balance2[0] is None:
        balance2 = (0,)
    if balance is None or balance[0] is None:
        balance = (0,)
    difference = balance[0] - balance2[0]

    cur.execute("SELECT SUM(CryptoAmount) FROM CryptoTransaction JOIN UserDetails ON UserDetails.UserId = CryptoTransaction.UserId WHERE UserDetails.UserName = %s AND CryptoTransaction.TransactionType='sold';", (username,))
    crypto_sold = cur.fetchone()
    if crypto_sold is None or crypto_sold[0] is None:
        crypto_sold = (0,)
    cur.execute("SELECT SUM(CryptoAmount) FROM CryptoTransaction JOIN UserDetails ON UserDetails.UserId = CryptoTransaction.UserId WHERE UserDetails.UserName = %s AND CryptoTransaction.TransactionType='bought';", (username,))
    crypto_bought = cur.fetchone()
    if crypto_bought is None or crypto_bought[0] is None:
        crypto_bought = (0,)
    crypto_balance = crypto_sold[0] - crypto_bought[0]

    cur.execute("SELECT SUM(StockAmount) FROM StockTransaction JOIN UserDetails ON UserDetails.UserId = StockTransaction.UserId WHERE UserDetails.UserName = %s AND StockTransaction.TransactionType='sold';", (username,))
    stock_sold = cur.fetchone()
    if stock_sold is None or stock_sold[0] is None:
        stock_sold = (0,)
    cur.execute("SELECT SUM(StockAmount) FROM StockTransaction JOIN UserDetails ON UserDetails.UserId = StockTransaction.UserId WHERE UserDetails.UserName = %s AND StockTransaction.TransactionType='bought';", (username,))
    stock_bought = cur.fetchone()
    if stock_bought is None or stock_bought[0] is None:
        stock_bought = (0,)
    stock_balance = stock_bought[0] - stock_sold[0]
    cur.execute("SELECT COUNT(*) AS transaction_count FROM UserTransaction JOIN UserDetails ON UserTransaction.UserId = UserDetails.UserId WHERE UserDetails.UserName = %s;", (username,))
    transnum = cur.fetchone()
    if transnum is None or transnum[0] is None:
        transnum = (0,)
    variable = difference+income[0]+crypto_balance-stock_balance
    new = balance2[0]+crypto_bought[0]+stock_bought[0]
    cur.execute("SELECT UserId from UserDetails WHERE UserName=%s;",(username,))
    con.commit()
    userid = cur.fetchone()
    values = budgetvalues(userid)
    return render_template('home.html', username=username, income=income[0], transnum=transnum[0], balance=variable, expenses = new, budget = values[4])


@app.route('/transactions/<username>', methods=['GET', 'POST'])
@login_required
def transactions(username):
    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = request.form['amount']
        type = request.form['type']
        add_transaction(username, date, category, amount, type)
        #return "Transaction added successfully."

    cur.execute("SELECT UserId FROM UserDetails WHERE UserName = %s;", (username,))
    con.commit()
    userid = cur.fetchone()
    cur.execute("SELECT * FROM UserTransaction WHERE UserId = %s;", (userid,))
    con.commit()
    elements = cur.fetchall()
    return render_template('transactions.html', elements=elements, username=username)

def add_transaction(username, date, category, amount, type):
    try:
        cur.execute("SELECT UserId FROM UserDetails WHERE UserName = %s;", (username,))
        con.commit()
        userid = cur.fetchone()
        cur.execute("INSERT INTO UserTransaction (UserId, Amount, Reason, TransactionType, TransactionDate) VALUES (%s, %s, %s, %s, %s);", (userid[0], amount, category, type, date))
        con.commit()
        print('Transaction added successfully')
    except Exception as e:
        print("Error adding transaction:", e)

@app.route('/delete_transaction/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    if request.form.get('_method') == 'DELETE':
        # Assuming you have a function `delete_transaction_by_id` to delete the transaction
        username =delete_transaction_by_id(transaction_id)
    
    return redirect(url_for('transactions', username=username[0]))

def delete_transaction_by_id(transaction_id):
    cur.execute("SELECT UserName FROM UserDetails JOIN UserTransaction ON UserTransaction.UserId = UserDetails.UserId WHERE UserTransaction.TransactionId =%s;", (transaction_id,))
    con.commit()
    username = cur.fetchone()
    delete_query = "DELETE FROM UserTransaction WHERE TransactionId = %s"
    cur.execute(delete_query, (transaction_id,))
    con.commit()
    print(f"Transaction {transaction_id} deleted successfully.")
    return username

@app.route('/add_income/<username>', methods=['GET', 'POST'])
@login_required
def add_income(username):
    if request.method == 'POST':
        date = request.form['date']
        amount = request.form['amount']
        input_income(username, date, amount)
        #return "Transaction added successfully."

    cur.execute("SELECT UserId FROM UserDetails WHERE UserName = %s;", (username,))
    con.commit()
    userid = cur.fetchone()
    cur.execute("SELECT * FROM UserMoney WHERE UserId = %s;", (userid,))
    con.commit()
    elements = cur.fetchall()
    return render_template('add_income.html', elements=elements, username=username)

def input_income(username, date, amount):
    try:
        cur.execute("SELECT UserId FROM UserDetails WHERE UserName = %s;", (username,))
        con.commit()
        userid = cur.fetchone()
        cur.execute("INSERT INTO UserMoney (UserId, UserIncome, IncomeDate) VALUES (%s, %s, %s);", (userid[0], amount, date))
        con.commit()
        print('Income added successfully')
    except Exception as e:
        print("Error adding income:", e)

@app.route('/delete_income/<int:income_id>', methods=['POST'])
def delete_income(income_id):
    if request.form.get('_method') == 'DELETE':
        # Assuming you have a function `delete_transaction_by_id` to delete the transaction
        username =delete_income_by_id(income_id)
    
    return redirect(url_for('add_income', username=username[0]))

def delete_income_by_id(income_id):
    cur.execute("SELECT UserName FROM UserDetails JOIN UserMoney ON UserMoney.UserId = UserDetails.UserId WHERE UserMoney.MoneyId =%s;", (income_id,))
    con.commit()
    username = cur.fetchone()
    delete_query = "DELETE FROM UserMoney WHERE MoneyId = %s"
    cur.execute(delete_query, (income_id,))
    con.commit()
    print(f"Income {income_id} deleted successfully.")
    return username
@app.route('/view_stats/<username>')
def view_stats(username):
    return render_template('stats.html', username=username)

@app.route('/data/today/<username>')
@login_required
def get_today_data(username):
    cur.execute("SELECT UserId FROM UserDetails WHERE UserName = %s;", (username,))
    con.commit()
    userid = cur.fetchone()
    print("yes",username)
  #  if userid:
   #     userid = userid[0]
   # else:
    #    return jsonify([])  # Handle case where username does not exist

    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        today_date = datetime.now().strftime('%Y-%m-%d')
        query = """
        SELECT reason AS category, SUM(amount) AS amount_spent
        FROM UserTransaction
        WHERE transactiontype = 'withdraw' AND transactiondate = %s AND userid = %s
        GROUP BY reason
        """
        cursor.execute(query, (today_date, userid,))
        data = cursor.fetchall()
        print(data , ":haha")
    return jsonify(data)

@app.route('/data/last30days/<username>')
@login_required
def get_last_30_days_data(username):
    cur.execute("SELECT UserId FROM UserDetails WHERE UserName = %s;", (username,))
    con.commit()
    userid = cur.fetchone()
    print("yes")
    if userid:
        userid = userid[0]
    else:
        
        return jsonify([])  # Handle case where username does not exist

    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        query = """
        SELECT reason AS category, SUM(amount) AS amount_spent
        FROM UserTransaction
        WHERE transactiontype = 'withdraw' AND transactiondate >= %s AND userid = %s
        GROUP BY reason
        """
        cursor.execute(query, (thirty_days_ago, userid,))
        data = cursor.fetchall()
        print(data)
    return jsonify(data)

@app.route('/update_crypto/<username>')
@login_required
def update_crypto(username):
    cur.execute("SELECT UserId FROM UserDetails WHERE UserName = %s;", (username,))
    con.commit()
    userid = cur.fetchone()[0]
    
    cur.execute("SELECT * FROM CryptoTransaction WHERE UserId = %s;", (userid,))
    con.commit()
    transactions = cur.fetchall()
    
    return render_template('crypto.html', username=username, transactions=transactions)

# Route to handle adding a new cryptocurrency transaction
@app.route('/add_crypto_transaction/<username>', methods=['GET', 'POST'])
@login_required
def add_crypto_transaction(username):
    if request.method == 'POST':
        crypto_name = request.form['crypto_name']
        crypto_amount = float(request.form['crypto_amount'])
        transaction_type = request.form['transaction_type']
        transaction_date = datetime.now().strftime('%Y-%m-%d')
        
        # Fetch the current price of the cryptocurrency
        try:
            response = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids={crypto_name}&vs_currencies=usd')
            if response.ok:
                data = response.json()
                current_price = data[crypto_name]['usd']
                total_amount = crypto_amount * current_price

                # Get the user ID
                cur.execute("SELECT UserId FROM UserDetails WHERE UserName = %s;", (username,))
                con.commit()
                userid = cur.fetchone()[0]
                
                # Insert the transaction into the database
                cur.execute("INSERT INTO CryptoTransaction (UserId, CryptoName, CryptoAmount, TransactionType, TransactionDate) VALUES (%s, %s, %s, %s, %s);",
                            (userid, crypto_name, total_amount, transaction_type, transaction_date))
                con.commit()
                return redirect(url_for('update_crypto'))
            else:
                print("Failed to fetch cryptocurrency price.")
        except Exception as e:
            print("Error fetching cryptocurrency price or adding transaction:", e)
    
    return redirect(url_for('update_crypto', username=username))

@app.route('/update_stock/<username>')
@login_required
def update_stock(username):
    cur.execute("SELECT UserId FROM UserDetails WHERE UserName = %s;", (username,))
    con.commit()
    userid = cur.fetchone()[0]
    
    cur.execute("SELECT * FROM StockTransaction WHERE UserId = %s;", (userid,))
    con.commit()
    transactions = cur.fetchall()
    
    return render_template('stock.html', username=username, transactions=transactions)

@app.route('/add_stock_transaction/<username>', methods=['GET', 'POST'])
@login_required
def add_stock_transaction(username):
    if request.method == 'POST':
        stock_name = request.form['stock_name']
        stock_amount = float(request.form['stock_amount'])
        transaction_type = request.form['transaction_type']
        transaction_date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            response = requests.get(f'https://api.twelvedata.com/price?symbol={stock_name}&apikey=07abf5199f644ea792f4382bc332dfc2')
            if response.ok:
                data = response.json()
                current_price = float(data['price'])
                total_amount = stock_amount * current_price

                cur.execute("SELECT UserId FROM UserDetails WHERE UserName = %s;", (username,))
                con.commit()
                userid = cur.fetchone()[0]
                
                cur.execute("INSERT INTO StockTransaction (UserId, StockName, StockAmount, TransactionType, TransactionDate) VALUES (%s, %s, %s, %s, %s);",
                            (userid, stock_name, total_amount, transaction_type, transaction_date))
                con.commit()
                return redirect(url_for('update_stock', username=username))
            else:
                print("Failed to fetch stock price.")
        except Exception as e:
            print("Error fetching stock price or adding transaction:", e)
            
    return redirect(url_for('update_stock', username=username))

@app.route('/budget/<username>', methods=['GET', 'POST'])
@login_required
def budget(username):
    cur.execute("SELECT UserId from UserDetails WHERE UserName=%s;",(username,))
    con.commit()
    userid = cur.fetchone()[0]
    if request.method == 'POST':
        category = request.form['category']
        amount = request.form['amount']
        updatevalues( userid , category , amount)

    values = budgetvalues(userid )
    spent_amount = spent(userid)[0]  # Your code to get the spent amount
    save = values[4] - Decimal(spent_amount)

    return render_template('budget.html',housing=values[0] , food = values[1] , entertainment=values[2] , others=values[3], overall=values[4], remaining=save, username=username)

def updatevalues(userid , category , amount):
    cur.execute("SELECT * FROM Budget WHERE UserId=%s AND Category=%s;",(userid , category))
    con.commit()
    prev = cur.fetchone()
    if prev == None or prev[0] == None:
        query = "INSERT INTO Budget (UserId , Category ,BudgetAmount) VALUES (%s ,%s ,%s);"
        cur.execute(query,(userid , category ,amount))
    else:
        query = "UPDATE Budget SET BudgetAmount=%s WHERE UserId =%s AND Category=%s;"
        cur.execute(query,(amount ,userid , category))
    con.commit()

def budgetvalues(userid):
    cur.execute("SELECT Category , BudgetAmount FROM Budget WHERE UserId =%s",(userid,))
    con.commit()
    valuelist = cur.fetchall()
    values=[0,0,0,0,0]
    for i in valuelist:
        if i[0]=='housing':
            values[0]=i[1]
        elif i[0]=='food':
            values[1]=i[1]
        elif i[0]=='entertainment':
            values[2]=i[1]
        elif i[0]=='others':
            values[3]=i[1]
    values[4]=values[0]+values[1]+values[2]+values[3]
    return values
def spent(userid):
    current_datetime = datetime.now()
    current_year_month = f"{current_datetime.year}-{current_datetime.month:02}"
    
    cur.execute("""
        SELECT SUM(Amount) AS total_amount
        FROM UserTransaction
        WHERE UserId = %s
          AND reason IN ('entertainment', 'others', 'electricity', 'food', 'grocery', 'rent')
          AND TO_CHAR(TransactionDate, 'YYYY-MM') = %s
          AND transactiontype = 'withdraw';
    """, (userid,current_year_month))
    con.commit()
    expense = cur.fetchone()
    if expense is None or expense[0] is None:
        return 0,
    else:
        return float(expense[0]),

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect(url_for('login'))
if __name__ == '__main__':
    app.run(debug=True)

cur.close()
con.close()

