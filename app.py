from flask import Flask, render_template, request, redirect, flash, session
import pandas as pd
import random
import os
from datetime import datetime
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import smtplib
from email.mime.text import MIMEText

# ---------------- CONFIG ----------------
TXN_FILE = "transactions.xlsx"
FILE_NAME = "accounts.xlsx"

EMAIL_ADDRESS = "scifigen4@gmail.com"
EMAIL_PASSWORD = "mnlirpbzrzztjico"


app = Flask(__name__)
app.secret_key = "bank123"

BRANCHES = [
    "Bangalore", "Mysore", "Chennai", "Hyderabad",
    "Mumbai", "Delhi", "Pune", "Kolkata",
    "Jaipur", "Coimbatore"
]

EMPLOYEES = ["emp1", "emp2", "emp3"]
PASSWORD = "1234"


# ---------------- OTP FUNCTIONS ----------------
def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp_email(receiver, otp):
    msg = MIMEText(f"Your Bank Login OTP is: {otp}")
    msg["Subject"] = "Bank Login Verification"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = receiver

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    server.send_message(msg)
    server.quit()


# ---------------- LOAD DATA ----------------
if os.path.exists(FILE_NAME):
    df = pd.read_excel(FILE_NAME, dtype=str)
else:
    df = pd.DataFrame()

required_cols = [
    "Name", "Phone", "Gender", "Aadhar", "Address",
    "AccountNo", "Branch", "CreatedBy",
    "Balance", "Status", "PIN",
    "LastDeposit", "LastWithdraw",
    "LastTransactionType", "LastTransactionAmount",
    "LastTransactionDate"
]

for col in required_cols:
    if col not in df.columns:
        if col == "Balance":
            df[col] = "0"
        elif col == "Status":
            df[col] = "Active"
        elif col == "PIN":
            df[col] = "0000"
        else:
            df[col] = ""

df.to_excel(FILE_NAME, index=False)


# ---------------- TRANSACTION FILE ----------------
if os.path.exists(TXN_FILE):
    txn_df = pd.read_excel(TXN_FILE, dtype=str)
else:
    txn_df = pd.DataFrame(columns=[
        "AccountNo",
        "Type",
        "Amount",
        "BalanceAfter",
        "DateTime"
    ])
    txn_df.to_excel(TXN_FILE, index=False)


# ---------------- SAVE ----------------
def save():
    global df
    try:
        df.to_excel(FILE_NAME, index=False)
    except PermissionError:
        print("⚠ Please close accounts.xlsx file and try again.")


# ---------------- TRANSACTION LOGGER ----------------
def log_transaction(acc, txn_type, amount, balance):
    global txn_df
    new_txn = {
        "AccountNo": acc,
        "Type": txn_type,
        "Amount": amount,
        "BalanceAfter": balance,
        "DateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    txn_df = pd.concat([txn_df, pd.DataFrame([new_txn])], ignore_index=True)
    txn_df.to_excel(TXN_FILE, index=False)


# ---------------- ACCOUNT NUMBER ----------------
def generate_account():
    return "".join(str(random.randint(0, 9)) for _ in range(12))


# ---------------- UNIFIED LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def unified_login():
    if request.method == "POST":
        role = request.form["role"]

        # -------- EMPLOYEE LOGIN --------
        if role == "employee":
            email = request.form["email"]
            pwd = request.form["password"]

            if pwd != PASSWORD:
                flash("❌ Invalid password")
                return redirect("/")

            otp = generate_otp()
            session["otp"] = otp
            session["email"] = email
            session["employee"] = email

            send_otp_email(email, otp)

            flash("📩 OTP sent to your email")
            return redirect("/verify-otp")

        # -------- CUSTOMER LOGIN --------
        elif role == "customer":
            acc = request.form["accountno"]
            aadhar = request.form["aadhar"]
            pin = request.form["pin"]

            user = df[
                (df["AccountNo"] == acc) &
                (df["Aadhar"] == aadhar) &
                (df["PIN"] == pin)
            ]

            if user.empty:
                flash("❌ Invalid customer login")
                return redirect("/")

            session["customer"] = acc
            return redirect("/customer-dashboard")

        else:
            flash("❌ Please select login role")
            return redirect("/")

    return render_template("login.html", branches=BRANCHES, employees=EMPLOYEES)


# ---------------- OTP VERIFY ----------------
@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        user_otp = request.form["otp"]

        if user_otp == session.get("otp"):
            session.pop("otp")
            return redirect("/dashboard")

        flash("❌ Invalid OTP")
        return redirect("/verify-otp")

    return render_template("verify_otp.html")


# ---------------- EMPLOYEE DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "employee" not in session:
        return redirect("/")
    return render_template("dashboard_employee.html")


# ---------------- CREATE PAGE ----------------
@app.route("/create-page")
def create_page():
    if "employee" not in session:
        return redirect("/")
    return render_template("create_account.html")


# ---------------- DEPOSIT PAGE ----------------
@app.route("/deposit-page")
def deposit_page():
    if "employee" not in session:
        return redirect("/")
    return render_template("deposit.html")


# ---------------- WITHDRAW PAGE ----------------
@app.route("/withdraw-page")
def withdraw_page():
    if "employee" not in session:
        return redirect("/")
    return render_template("withdraw.html")


# ---------------- CLOSE PAGE ----------------
@app.route("/close-page")
def close_page():
    if "employee" not in session:
        return redirect("/")
    return render_template("close_account.html")


# ---------------- TRANSACTION PAGE ----------------
@app.route("/transactions/<acc>")
def transactions(acc):
    user_txns = txn_df[txn_df["AccountNo"] == acc]
    return render_template("transactions.html", tables=user_txns.to_html(index=False))


# ---------------- CREATE ACCOUNT ----------------
@app.route("/create", methods=["POST"])
def create_account():
    global df

    name = request.form["name"]
    phone = request.form["phone"]
    gender = request.form["gender"]
    aadhar = request.form["aadhar"]
    address = request.form["address"]
    opening_deposit = float(request.form["deposit"])
    pin = request.form["pin"]

    if opening_deposit < 500:
        flash("❌ Minimum opening deposit is ₹500")
        return redirect("/create-page")

    if phone in df["Phone"].astype(str).values:
        flash("❌ Phone number already exists")
        return redirect("/create-page")

    acc_no = generate_account()

    new_row = {
        "Name": name,
        "Phone": phone,
        "Gender": gender,
        "Aadhar": aadhar,
        "Address": address,
        "AccountNo": acc_no,
        "Branch": session.get("branch", ""),
        "CreatedBy": session.get("employee", ""),
        "Balance": str(opening_deposit),
        "Status": "Active",
        "LastDeposit": opening_deposit,
        "LastWithdraw": "",
        "LastTransactionType": "Deposit",
        "LastTransactionAmount": opening_deposit,
        "LastTransactionDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "PIN": pin
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save()
    log_transaction(acc_no, "Deposit", opening_deposit, opening_deposit)

    flash(f"✅ Account created successfully! Account No: {acc_no}")
    return redirect("/dashboard")


# ---------------- DEPOSIT ----------------
@app.route("/deposit", methods=["POST"])
def deposit():
    global df
    acc = request.form["accountno"]
    amount = float(request.form["amount"])

    idx = df[df["AccountNo"] == acc].index
    if len(idx) == 0:
        flash("❌ Account not found")
        return redirect("/deposit-page")

    idx = idx[0]
    current_balance = float(df.at[idx, "Balance"])
    new_balance = current_balance + amount

    df.at[idx, "Balance"] = str(new_balance)
    df.at[idx, "LastDeposit"] = amount
    df.at[idx, "LastTransactionType"] = "Deposit"
    df.at[idx, "LastTransactionAmount"] = amount
    df.at[idx, "LastTransactionDate"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save()
    log_transaction(acc, "Deposit", amount, new_balance)

    flash(f"✅ Deposit successful! Current Balance: ₹{new_balance}")
    return redirect("/deposit-page")


# ---------------- WITHDRAW ----------------
@app.route("/withdraw", methods=["POST"])
def withdraw():
    global df
    acc = request.form["accountno"]
    amount = float(request.form["amount"])

    idx = df[df["AccountNo"] == acc].index
    if len(idx) == 0:
        flash("❌ Account not found")
        return redirect("/withdraw-page")

    idx = idx[0]
    balance = float(df.at[idx, "Balance"])

    if amount > balance:
        flash(f"❌ Insufficient balance! Available: ₹{balance}")
        return redirect("/withdraw-page")

    new_balance = balance - amount

    df.at[idx, "Balance"] = str(new_balance)
    df.at[idx, "LastWithdraw"] = amount
    df.at[idx, "LastTransactionType"] = "Withdraw"
    df.at[idx, "LastTransactionAmount"] = amount
    df.at[idx, "LastTransactionDate"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save()
    log_transaction(acc, "Withdraw", amount, new_balance)

    flash(f"✅ Withdrawal successful! Current Balance: ₹{new_balance}")
    return redirect("/withdraw-page")


# ---------------- CLOSE ACCOUNT ----------------
@app.route("/close", methods=["POST"])
def close_account():
    global df
    acc = request.form["accountno"]

    idx = df[df["AccountNo"] == acc].index
    if len(idx) == 0:
        flash("❌ Account not found")
        return redirect("/close-page")

    idx = idx[0]
    balance = float(df.at[idx, "Balance"])

    if balance < 250:
        flash("❌ Minimum ₹250 balance required to close account")
        return redirect("/close-page")

    df.at[idx, "Balance"] = str(balance - 150)
    df.at[idx, "Status"] = "Closed"
    save()

    flash("✅ Account closed successfully (₹150 charged)")
    return redirect("/dashboard")


# ---------------- CUSTOMER DASHBOARD ----------------
@app.route("/customer-dashboard")
def customer_dashboard():
    acc = session.get("customer")
    user = df[df["AccountNo"] == acc].iloc[0]
    return render_template("dashboard_customer.html", balance=user["Balance"])


# ---------------- ADMIN CHARTS ----------------
@app.route("/admin-charts")
def charts():
    os.makedirs("static", exist_ok=True)

    deposits = txn_df[txn_df["Type"] == "Deposit"]["Amount"].astype(float).sum()
    withdraws = txn_df[txn_df["Type"] == "Withdraw"]["Amount"].astype(float).sum()

    plt.figure()
    plt.bar(["Deposits", "Withdrawals"], [deposits, withdraws])
    plt.savefig("static/chart.png")
    plt.close()

    return render_template("charts.html")


# ---------------- PDF STATEMENT ----------------
@app.route("/statement/<acc>")
def statement(acc):
    user_txns = txn_df[txn_df["AccountNo"] == acc]

    file = f"statement_{acc}.pdf"
    c = canvas.Canvas(file, pagesize=A4)
    y = 800

    c.drawString(50, y, f"Statement for Account: {acc}")
    y -= 40

    for _, row in user_txns.iterrows():
        line = f"{row['DateTime']} | {row['Type']} | ₹{row['Amount']} | Bal ₹{row['BalanceAfter']}"
        c.drawString(50, y, line)
        y -= 20

    c.save()
    return f"PDF Generated: {file}"


# ---------------- ADMIN REPORT ----------------
@app.route("/admin-report")
def report():
    total = len(df)
    active = len(df[df["Status"] == "Active"])
    closed = len(df[df["Status"] == "Closed"])
    total_balance = df["Balance"].astype(float).sum()

    return f"""
    Total Accounts: {total}<br>
    Active Accounts: {active}<br>
    Closed Accounts: {closed}<br>
    Total Bank Balance: ₹{total_balance}
    """


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)
