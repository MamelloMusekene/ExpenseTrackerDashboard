from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    make_response,
    url_for,
    flash
)

from flask_bcrypt import Bcrypt
from database import create_database

from datetime import datetime

import sqlite3

# -------------------------------------------------------
# Create Database
# -------------------------------------------------------

create_database()

# -------------------------------------------------------
# Flask App Configuration
# -------------------------------------------------------

app = Flask(__name__)

app.secret_key = "change_this_to_a_long_random_secret_key"

bcrypt = Bcrypt(app)

DATABASE = "database.db"


# -------------------------------------------------------
# Database Connection Helper
# -------------------------------------------------------

def get_db_connection():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


# -------------------------------------------------------
# Home Page
# -------------------------------------------------------

@app.route("/")
def home():

    return render_template("index.html")


# -------------------------------------------------------
# Register
# -------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"].strip()

        email = request.form["email"].strip().lower()

        password = request.form["password"]

        conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email=?",
            (email,)
        )

        if cursor.fetchone():

            conn.close()

            return "Email already registered."

        hashed_password = bcrypt.generate_password_hash(
            password
        ).decode("utf-8")

        cursor.execute(
            """
            INSERT INTO users
            (username,email,password)

            VALUES
            (?,?,?)
            """,
            (
                username,
                email,
                hashed_password
            )
        )

        conn.commit()

        conn.close()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# -------------------------------------------------------
# Login
# -------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()

        password = request.form["password"]

        conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute(

            """
            SELECT *
            FROM users

            WHERE email=?
            """,

            (email,)
        )

        user = cursor.fetchone()

        conn.close()

        if user and bcrypt.check_password_hash(
                user["password"],
                password
        ):

            session["user_id"] = user["id"]

            session["username"] = user["username"]

            flash("Welcome back! Login successful.", "success")

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

        return redirect(url_for("login"))

    return render_template("login.html")

# -------------------------------------------------------
# Dashboard
# -------------------------------------------------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    search = request.args.get("search", "").strip()
    month = request.args.get("month", "")

    today = datetime.now().strftime("%d %B %Y")

    conn = get_db_connection()

    cursor = conn.cursor()

    # --------------------------------------------
    # Transactions (Search + Month Filter)
    # --------------------------------------------

    query = """
        SELECT *
        FROM transactions
        WHERE user_id=?
    """

    params = [user_id]

    if search:
        query += " AND category LIKE ?"
        params.append(f"%{search}%")

    if month:
        query += " AND date LIKE ?"
        params.append(f"{month}%")

    query += " ORDER BY id DESC"

    cursor.execute(query, tuple(params))

    transactions = cursor.fetchall()

    # --------------------------------------------
    # Total Income
    # --------------------------------------------

    cursor.execute("""
        SELECT IFNULL(SUM(amount),0)
        FROM transactions
        WHERE user_id=?
        AND type='Income'
    """, (user_id,))

    total_income = cursor.fetchone()[0]

    # --------------------------------------------
    # Total Expenses
    # --------------------------------------------

    cursor.execute("""
        SELECT IFNULL(SUM(amount),0)
        FROM transactions
        WHERE user_id=?
        AND type='Expense'
    """, (user_id,))

    total_expenses = cursor.fetchone()[0]

    balance = total_income - total_expenses

    # --------------------------------------------
    # Largest Income
    # --------------------------------------------

    cursor.execute("""
        SELECT IFNULL(MAX(amount),0)
        FROM transactions
        WHERE user_id=?
        AND type='Income'
    """, (user_id,))

    max_income = cursor.fetchone()[0]

    # --------------------------------------------
    # Largest Expense
    # --------------------------------------------

    cursor.execute("""
        SELECT IFNULL(MAX(amount),0)
        FROM transactions
        WHERE user_id=?
        AND type='Expense'
    """, (user_id,))

    max_expense = cursor.fetchone()[0]

    # --------------------------------------------
    # Average Expense
    # --------------------------------------------

    cursor.execute("""
        SELECT IFNULL(AVG(amount),0)
        FROM transactions
        WHERE user_id=?
        AND type='Expense'
    """, (user_id,))

    average_expense = cursor.fetchone()[0]

    # --------------------------------------------
    # Expense Count
    # --------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM transactions
        WHERE user_id=?
        AND type='Expense'
    """, (user_id,))

    expense_count = cursor.fetchone()[0]

    # --------------------------------------------
    # Highest Spending Category
    # --------------------------------------------

    cursor.execute("""
        SELECT category,
               SUM(amount) AS total
        FROM transactions
        WHERE user_id=?
        AND type='Expense'
        GROUP BY category
        ORDER BY total DESC
        LIMIT 1
    """, (user_id,))

    top_category = cursor.fetchone()

    if top_category:
        top_category = top_category["category"]
    else:
        top_category = "None"

    # --------------------------------------------
    # Pie Chart
    # --------------------------------------------

    cursor.execute("""
        SELECT category,
               SUM(amount) AS total
        FROM transactions
        WHERE user_id=?
        AND type='Expense'
        GROUP BY category
    """, (user_id,))

    category_data = cursor.fetchall()

    labels = []
    values = []

    for row in category_data:
        labels.append(row["category"])
        values.append(row["total"])

    conn.close()

    return render_template(

        "dashboard.html",

        today=today,

        transactions=transactions,

        total_income=total_income,

        total_expenses=total_expenses,

        balance=balance,

        max_income=max_income,

        max_expense=max_expense,

        average_expense=average_expense,

        expense_count=expense_count,

        top_category=top_category,

        labels=labels,

        values=values,

        search=search,

        month=month

    )

# -------------------------------------------------------
# Add Transaction
# -------------------------------------------------------

@app.route("/add", methods=["POST"])
def add_transaction():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    transaction_type = request.form["type"]
    category = request.form["category"]
    amount = float(request.form["amount"])
    date = request.form["date"]

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO transactions
        (user_id, type, category, amount, date)

        VALUES
        (?, ?, ?, ?, ?)
    """, (
        user_id,
        transaction_type,
        category,
        amount,
        date
    ))

    conn.commit()
    conn.close()

    flash("Transaction added successfully!", "success")
    return redirect(url_for("dashboard"))


# -------------------------------------------------------
# Edit Transaction
# -------------------------------------------------------

@app.route("/edit/<int:id>")
def edit_transaction(id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM transactions
        WHERE id=?
        AND user_id=?
    """, (
        id,
        session["user_id"]
    ))

    transaction = cursor.fetchone()

    conn.close()

    if transaction is None:
        return "Transaction not found."

    return render_template(
        "edit.html",
        transaction=transaction
    )


# -------------------------------------------------------
# Update Transaction
# -------------------------------------------------------

@app.route("/update/<int:id>", methods=["POST"])
def update_transaction(id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    transaction_type = request.form["type"]
    category = request.form["category"]
    amount = float(request.form["amount"])
    date = request.form["date"]

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE transactions

        SET

        type=?,
        category=?,
        amount=?,
        date=?

        WHERE id=?
        AND user_id=?
    """, (

        transaction_type,
        category,
        amount,
        date,
        id,
        session["user_id"]

    ))

    conn.commit()
    conn.close()

    flash("Transaction updated successfully!", "success")
    return redirect(url_for("dashboard"))


# -------------------------------------------------------
# Delete Transaction
# -------------------------------------------------------

@app.route("/delete/<int:id>")
def delete_transaction(id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE
        FROM transactions

        WHERE id=?
        AND user_id=?
    """, (
        id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    flash("Transaction deleted successfully!", "success")
    return redirect(url_for("dashboard"))


# -------------------------------------------------------
# Export CSV
# -------------------------------------------------------

@app.route("/export")
def export_csv():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            type,
            category,
            amount,
            date
        FROM transactions
        WHERE user_id=?
        ORDER BY date DESC
    """, (
        session["user_id"],
    ))

    rows = cursor.fetchall()

    conn.close()

    output = []

    output.append("Type,Category,Amount,Date")

    for row in rows:

        output.append(
            f'{row["type"]},'
            f'{row["category"]},'
            f'{row["amount"]},'
            f'{row["date"]}'
        )

    csv_data = "\n".join(output)

    response = make_response(csv_data)

    response.headers["Content-Disposition"] = (
        "attachment; filename=transactions.csv"
    )

    response.headers["Content-Type"] = "text/csv"

    return response


# -------------------------------------------------------
# Reports
# -------------------------------------------------------

@app.route("/reports")
def reports():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db_connection()

    cursor = conn.cursor()

# Monthly report
    cursor.execute("""
        SELECT

            substr(date,1,7) AS month,

            SUM(
                CASE
                    WHEN type='Income'
                    THEN amount
                    ELSE 0
                END
            ) AS income,

            SUM(
                CASE
                    WHEN type='Expense'
                    THEN amount
                    ELSE 0
                END
            ) AS expenses

        FROM transactions

        WHERE user_id=?

        GROUP BY month

        ORDER BY month
    """, (user_id,))

    rows = cursor.fetchall()

    months = []
    income_values = []
    expense_values = []

    for row in rows:

        months.append(row["month"])
        income_values.append(row["income"])
        expense_values.append(row["expenses"])

# Dashboard totals
    cursor.execute("""
        SELECT IFNULL(SUM(amount),0)
        FROM transactions
        WHERE user_id=? AND type='Income'
    """, (user_id,))
    total_income = cursor.fetchone()[0]

    cursor.execute("""
        SELECT IFNULL(SUM(amount),0)
        FROM transactions
        WHERE user_id=? AND type='Expense'
    """, (user_id,))
    total_expenses = cursor.fetchone()[0]

    balance = total_income - total_expenses

    conn.close()
   

    return render_template(

        "reports.html",

        months=months,
        income_values=income_values,
        expense_values=expense_values,
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance

    )

# -------------------------------------------------------
# Logout
# -------------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()
    flash("You have been logged out successfully.", "success")

    return redirect(url_for("home"))

# -------------------------------------------------------
# Run Application
# -------------------------------------------------------

if __name__ == "__main__":

    create_database()

    app.run(
        debug=True
    )
