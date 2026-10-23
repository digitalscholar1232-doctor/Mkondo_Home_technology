import os
import hashlib
import secrets
from datetime import datetime
from decimal import Decimal

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import (
    create_engine, text, MetaData, Table, Column, Integer, String,
    Numeric, DateTime, ForeignKey, Boolean
)
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

APP_NAME = "Mkondo Home Technology"
DEFAULT_DB = os.getenv("DATABASE_URL", "sqlite:///mkondo_dev.db")

st.set_page_config(page_title=APP_NAME, page_icon="🔗", layout="wide")

# CSS 
def load_css():
    css_path = os.path.join(os.path.dirname(__file__), "style.css")
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except OSError:
        pass

load_css()

# Database 
def get_database_url():
    url = os.getenv("DATABASE_URL", DEFAULT_DB)
    # Render PostgreSQL URLs commonly start with postgres://; SQLAlchemy expects postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

@st.cache_resource
def get_engine():
    return create_engine(get_database_url(), pool_pre_ping=True, future=True)

metadata = MetaData()
users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True),
    Column("legal_name", String(120), nullable=False),
    Column("username", String(50), unique=True, nullable=False),
    Column("email", String(160), unique=True, nullable=False),
    Column("phone", String(40), nullable=False),
    Column("password_hash", String(256), nullable=False),
    Column("referral_id", String(24), unique=True, nullable=False),
    Column("referred_by", String(24), nullable=True),
    Column("is_admin", Boolean, nullable=False, default=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
)
transactions = Table(
    "transactions", metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("kind", String(30), nullable=False),  # sale_commission, withdrawal, membership_payment
    Column("amount", Numeric(12, 2), nullable=False),
    Column("status", String(20), nullable=False, default="pending"),
    Column("description", String(255), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("reviewed_by", String(50), nullable=True),
)
product_sales = Table(
    "product_sales", metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("product_name", String(160), nullable=False),
    Column("sale_amount", Numeric(12, 2), nullable=False),
    Column("customer_reference", String(120), nullable=False),
    Column("status", String(20), nullable=False, default="pending"),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("reviewed_by", String(50), nullable=True),
)

def init_db():
    metadata.create_all(get_engine())

def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
    return f"{salt}${digest}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
        return secrets.compare_digest(hash_password(password, salt).split("$", 1)[1], digest)
    except Exception:
        return False

def create_referral_id():
    return "MK" + secrets.token_hex(4).upper()

def fetch_user_by_username(username):
    with get_engine().connect() as conn:
        return conn.execute(
            text("SELECT * FROM users WHERE lower(username)=lower(:u)"),
            {"u": username.strip()}
        ).mappings().first()

def fetch_user_by_email(email):
    with get_engine().connect() as conn:
        return conn.execute(
            text("SELECT * FROM users WHERE lower(email)=lower(:e)"),
            {"e": email.strip()}
        ).mappings().first()

def create_user(legal_name, username, email, phone, password, referral_code=""):
    if fetch_user_by_username(username):
        raise ValueError("This Username already used.")
    if fetch_user_by_email(email):
        raise ValueError("This Email has Alread used.")
    referral_id = create_referral_id()
    referred_by = None
    if referral_code.strip():
        with get_engine().connect() as conn:
            referrer = conn.execute(
                text("SELECT referral_id FROM users WHERE referral_id=:r"),
                {"r": referral_code.strip().upper()}
            ).first()
        if not referrer:
            raise ValueError("Referral ID not found")
        referred_by = referrer[0]
    with get_engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO users
            (legal_name, username, email, phone, password_hash, referral_id, referred_by, is_admin, created_at)
            VALUES (:legal_name, :username, :email, :phone, :password_hash, :referral_id, :referred_by, :is_admin, :created_at)
        """), {
            "legal_name": legal_name.strip(),
            "username": username.strip(),
            "email": email.strip().lower(),
            "phone": phone.strip(),
            "password_hash": hash_password(password),
            "referral_id": referral_id,
            "referred_by": referred_by,
            "is_admin": False,
            "created_at": datetime.utcnow(),
        })
    return referral_id

def ensure_admin():
    admin_user = os.getenv("ADMIN_USERNAME", "GEORGE2002")
    admin_password = os.getenv("ADMIN")
    if not admin_password:
        # Do not hard-code the supplied admin password in source code.
        return
    with get_engine().begin() as conn:
        existing = conn.execute(text("SELECT id FROM users WHERE lower(username)=lower(:u)"),
                                {"u": admin_user}).first()
        if existing:
            conn.execute(text("UPDATE users SET is_admin=TRUE WHERE id=:id"), {"id": existing[0]})
        else:
            conn.execute(text("""
                INSERT INTO users
                (legal_name, username, email, phone, password_hash, referral_id, referred_by, is_admin, created_at)
                VALUES (:name, :username, :email, :phone, :phash, :ref, NULL, TRUE, :created)
            """), {
                "name": "System Administrator",
                "username": admin_user,
                "email": os.getenv("ADMIN_EMAIL", "admin@example.com"),
                "phone": os.getenv("ADMIN_PHONE", "Not provided"),
                "phash": hash_password(admin_password),
                "ref": create_referral_id(),
                "created": datetime.utcnow(),
            })

def money(value):
    try:
        return f"TSh {float(value):,.0f}"
    except (TypeError, ValueError):
        return "TSh 0"

def user_balance(user_id):
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT COALESCE(SUM(CASE
                WHEN status='approved' AND kind IN ('sale_commission') THEN amount
                WHEN status='approved' AND kind='withdrawal' THEN -amount
                ELSE 0 END), 0)
            FROM transactions WHERE user_id=:uid
        """), {"uid": user_id}).scalar()
    return Decimal(str(rows or 0))

def add_transaction(user_id, kind, amount, status, description):
    with get_engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO transactions (user_id, kind, amount, status, description, created_at)
            VALUES (:uid, :kind, :amount, :status, :description, :created)
        """), {"uid": user_id, "kind": kind, "amount": amount, "status": status,
               "description": description, "created": datetime.utcnow()})

def current_user():
    return st.session_state.get("user")

# Initialize 
try:
    init_db()
    ensure_admin()
except Exception as e:
    st.error("Database not connected.")
    st.code(str(e))
    st.stop()

# Sidebar / branding 
with st.sidebar:
    image_path = os.path.join(os.path.dirname(__file__), "images", "mkondo.png")
    if os.path.exists(image_path):
        st.image(image_path, use_container_width=True)
    else:
        st.markdown('<div class="brand-mark">MKONDO</div>', unsafe_allow_html=True)
    st.markdown("### Mkondo Home Technology")
    st.caption("Digital Marketing • Affiliate Marketing")
    st.divider()

    if current_user():
        st.success(f"Welcome, {current_user()['username']}")
        page = st.radio(
            "MENU",
            ["Dashboard", "Referral Network (My Team)", "Submit Product Sale",
             "Wallet & Transactions", "Profile", "Admin Panel" if current_user().get("is_admin") else "Help"],
            label_visibility="collapsed"
        )
        if st.button("Logout",use_container_width=True,):
            st.session_state.pop("user", None)
            st.rerun()
    else:
        page = st.radio("MENU", ["Home", "Login", "Sign Up"], label_visibility="collapsed")
        # Buttons on the public home page can switch to Login/Sign Up.
        page = st.session_state.get("public_page", page)

# Public pages 
if not current_user():
    if page == "Home":
        st.markdown(
            '<div class="hero"><div class="eyebrow">DIGITAL BUSINESS • AFFILIATE MARKETING</div>'
            '<h1>Mkondo Home Technology</h1>'
            '<p class="ticker">Welcome to Mkondo Home Technology — The Most Updated Business Center</p>'
            '<p>Promote products, connect customers with businesses, and track eligible commissions from verified sales.</p>'
            '<a class="hero-link" href="#get-started">Get Started ↓</a></div>',
            unsafe_allow_html=True
        )
        st.markdown('<div id="get-started"></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown('<div class="feature-card"><h3>📣 Digital Marketing</h3><p>Promote products and help businesses reach new customers.</p></div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="feature-card"><h3>🔗 Affiliate Marketing</h3><p>Share referral links and grow a network Worldwide.</p></div>', unsafe_allow_html=True)
        with c3:
            st.markdown('<div class="feature-card"><h3>📊 Clear Reporting</h3><p>Track submitted sales, approved commissions, and wallet activity.</p></div>', unsafe_allow_html=True)
        st.info("Bussiness policy: As More you Grow As more you Earn.")
        a, b = st.columns(2)
        with a:
            if st.button("Create Account", use_container_width=True):
                st.session_state["public_page"] = "Sign Up"
                st.rerun()
        with b:
            if st.button("Login", use_container_width=True):
                st.session_state["public_page"] = "Login"
                st.rerun()
        if "public_page" in st.session_state:
            st.session_state["public_page"] = st.session_state["public_page"]
    elif page == "Sign Up" or st.session_state.get("public_page") == "Sign Up":
        st.markdown("## Create your account")
        st.caption("Please Create your Account to start a Bussiness.")
        with st.form("signup_form"):
            legal_name = st.text_input("Legal name")
            username = st.text_input("Username")
            email = st.text_input("Email")
            phone = st.text_input("Phone number")
            referral_code = st.text_input("Referral ID (optional)")
            password = st.text_input("Password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            accepted = st.checkbox("I have understand that Money Released Based on Verified Affiliate System.")
            submitted = st.form_submit_button("Create Account")
        if submitted:
            if not all([legal_name.strip(), username.strip(), email.strip(), phone.strip(), password]):
                st.error("Please all requared Requared Details.")
            elif password != confirm:
                st.error("Passwords are Difference.")
            elif len(password) < 10:
                st.error("Password should be atleast 10 Letters/numbers.")
            elif not accepted:
                st.error("Please Agree That you have understand rules.")
            else:
                try:
                    referral_id = create_user(legal_name, username, email, phone, password, referral_code)
                    st.success(f"Account created Successful! Referral ID is: {referral_id}.Now go to Login section.")
                except (ValueError, SQLAlchemyError) as e:
                    st.error(str(e))
    else:  # Login
        st.markdown("## Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
        if submitted:
            record = fetch_user_by_username(username)
            if record and verify_password(password, record["password_hash"]):
                st.session_state["user"] = dict(record)
                st.session_state.pop("public_page", None)
                st.rerun()
            else:
                st.error("Username au password is incorrect.")
    st.stop()

#Authenticated pages 
user = current_user()
user_id = user["id"]

if page == "Dashboard":
    st.markdown(f"# Welcome, {user['username']} 👋")
    st.markdown("Welcome to Mkondo Home Technology The Home of Bussiness.")
    balance = user_balance(user_id)
    with get_engine().connect() as conn:
        team_count = conn.execute(text("SELECT COUNT(*) FROM users WHERE referred_by=:r"),
                                  {"r": user["referral_id"]}).scalar() or 0
        sale_count = conn.execute(text("SELECT COUNT(*) FROM product_sales WHERE user_id=:u AND status='approved'"),
                                  {"u": user_id}).scalar() or 0
        tx = pd.read_sql(text("SELECT kind, amount, status, created_at FROM transactions WHERE user_id=:u ORDER BY id DESC LIMIT 30"),
                         conn, params={"u": user_id})
    c1, c2, c3 = st.columns(3)
    c1.metric("Available balance", money(balance))
    c2.metric("Direct referrals", int(team_count))
    c3.metric("Approved sales", int(sale_count))
    st.subheader("Business activity")
    if not tx.empty:
        tx["amount"] = pd.to_numeric(tx["amount"], errors="coerce").fillna(0)
        chart = px.pie(tx, names="kind", values="amount", title="Transaction amounts by type", hole=0.48)
        st.plotly_chart(chart, use_container_width=True)
        st.dataframe(tx, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions Now.Kindly Submit payment Proof To be verified by Management Officer.")

elif page == "Referral Network (My Team)":
    st.title("Referral Network — My Team")
    st.write("Your Referral ID:")
    st.code(user["referral_id"])
    with get_engine().connect() as conn:
        team = pd.read_sql(text("""
            SELECT legal_name, username, referral_id, created_at
            FROM users WHERE referred_by=:r ORDER BY created_at DESC
        """), conn, params={"r": user["referral_id"]})
    st.subheader("Direct referrals")
    if team.empty:
        st.info("Sorry No one has Joined Bussiness Through your Referral ID.")
    else:
        st.dataframe(team, use_container_width=True, hide_index=True)
    st.caption("Now This Page show direct referrals.")

elif page == "Submit Product Sale":
    st.title("Submit Product Sale")
    st.write("Send Real Sales informations.")
    with st.form("sale_form"):
        product_name = st.text_input("Product/service name")
        sale_amount = st.number_input("Sale amount (TSh)", min_value=1.0, step=1000.0)
        customer_reference = st.text_input("Customer Referal Id")
        submitted = st.form_submit_button("Submit sale for review")
    if submitted:
        if not product_name.strip() or not customer_reference.strip():
            st.error("Write Customer Referal Id")
        else:
            with get_engine().begin() as conn:
                conn.execute(text("""
                    INSERT INTO product_sales (user_id, product_name, sale_amount, customer_reference, status, created_at)
                    VALUES (:u, :p, :a, :c, 'pending', :d)
                """), {"u": user_id, "p": product_name.strip(), "a": sale_amount,
                       "c": customer_reference.strip(), "d": datetime.utcnow()})
            st.success("Request Submitted successfully to Admin for Verification.")

    with get_engine().connect() as conn:
        sales = pd.read_sql(text("SELECT product_name, sale_amount, customer_reference, status, created_at FROM product_sales WHERE user_id=:u ORDER BY id DESC"),
                            conn, params={"u": user_id})
    st.subheader("My submitted sales")
    st.dataframe(sales, use_container_width=True, hide_index=True)

elif page == "Wallet & Transactions":
    st.title("Wallet & Transactions")
    balance = user_balance(user_id)
    st.metric("Available balance", money(balance))
    st.caption("Minimum withdrawal: TSh 40,000. Withdrawals require admin review.")
    with st.form("withdraw_form"):
        amount = st.number_input("Withdrawal amount (TSh)", min_value=40000.0, step=5000.0)
        method = st.selectbox("Payout method", ["M-Pesa", "Tigo Pesa", "Airtel Money", "Bank"])
        account = st.text_input("Payout phone/account")
        requested = st.form_submit_button("Request withdrawal")
    if requested:
        if Decimal(str(amount)) > balance:
            st.error("Available Balance is less than Minimum Withdral Amount.")
        elif not account.strip():
            st.error("Fill payment Phone account.")
        else:
            add_transaction(user_id, "withdrawal", amount, "pending", f"Withdrawal request: {method} / {account.strip()}")
            st.success("Withdrawal Request has Recieved by Admin Please Wait for Corfimation")
    with get_engine().connect() as conn:
        tx = pd.read_sql(text("SELECT kind, amount, status, description, created_at FROM transactions WHERE user_id=:u ORDER BY id DESC"),
                         conn, params={"u": user_id})
    st.dataframe(tx, use_container_width=True, hide_index=True)

elif page == "Profile":
    st.title("My Profile")
    st.text_input("Legal name", value=user["legal_name"], disabled=True)
    st.text_input("Username", value=user["username"], disabled=True)
    st.text_input("Referral ID", value=user["referral_id"], disabled=True)
    st.text_input("Phone number", value=user["phone"], disabled=True)
    st.text_input("Email", value=user["email"], disabled=True,)

elif page == "Admin Panel" and user.get("is_admin"):
    st.title("Admin Panel")
    st.warning("Admin actions change financial records. Review evidence before approving any transaction.")
    with get_engine().connect() as conn:
        pending_sales = pd.read_sql(text("""
            SELECT ps.id, ps.user_id, u.username, ps.product_name, ps.sale_amount, ps.customer_reference, ps.created_at
            FROM product_sales ps JOIN users u ON u.id=ps.user_id WHERE ps.status='pending' ORDER BY ps.id
        """), conn)
        pending_tx = pd.read_sql(text("""
            SELECT t.id, t.user_id, u.username, t.kind, t.amount, t.description, t.created_at
            FROM transactions t JOIN users u ON u.id=t.user_id WHERE t.status='pending' ORDER BY t.id
        """), conn)
    st.subheader("Pending product sales")
    st.dataframe(pending_sales, use_container_width=True, hide_index=True)
    if not pending_sales.empty:
        sale_id = st.number_input("Sale ID to review", min_value=1, step=1, key="sale_id")
        x, y = st.columns(2)
        if x.button("Approve sale"):
            with get_engine().begin() as conn:
                row = conn.execute(text("SELECT * FROM product_sales WHERE id=:id AND status='pending'"),
                                   {"id": int(sale_id)}).mappings().first()
                if row:
                    conn.execute(text("UPDATE product_sales SET status='approved', reviewed_by=:admin WHERE id=:id"),
                                 {"admin": user["username"], "id": int(sale_id)})
                    
                    # Pay the configured upline commissions only after a genuine product sale is approved.
                    # Levels are based on referral ancestry, not merely on joining or paying a membership fee.
                    amounts = [Decimal("5000"), Decimal("3000"), Decimal("1000")]
                    current_referral = conn.execute(
                        text("SELECT referred_by FROM users WHERE id=:uid"), {"uid": row["user_id"]}
                    ).scalar()
                    for level, commission_amount in enumerate(amounts, start=1):
                        if not current_referral:
                            break
                        upline = conn.execute(
                            text("SELECT id, referred_by FROM users WHERE referral_id=:r"),
                            {"r": current_referral}
                        ).mappings().first()
                        if not upline:
                            break
                        conn.execute(text("""
                            INSERT INTO transactions (user_id, kind, amount, status, description, created_at, reviewed_by)
                            VALUES (:uid, 'sale_commission', :amount, 'approved', :description, :created, :admin)
                        """), {
                            "uid": upline["id"],
                            "amount": commission_amount,
                            "description": f"Level {level} commission for approved product sale #{int(sale_id)}",
                            "created": datetime.utcnow(),
                            "admin": user["username"],
                        })
                        current_referral = upline["referred_by"]
                    st.success("Sale approved. Eligible upline commissions were recorded under the sales-based policy.")
                    st.rerun()
                else:
                    st.error("No Pending sale ID Found.")
        if y.button("Reject sale"):
            with get_engine().begin() as conn:
                conn.execute(text("UPDATE product_sales SET status='rejected', reviewed_by=:admin WHERE id=:id AND status='pending'"),
                             {"admin": user["username"], "id": int(sale_id)})
            st.rerun()

    st.subheader("Pending wallet transactions")
    st.dataframe(pending_tx, use_container_width=True, hide_index=True)
    if not pending_tx.empty:
        tx_id = st.number_input("Transaction ID to review", min_value=1, step=1, key="tx_id")
        x, y = st.columns(2)
        if x.button("Approve transaction"):
            with get_engine().begin() as conn:
                row = conn.execute(text("SELECT * FROM transactions WHERE id=:id AND status='pending'"),
                                   {"id": int(tx_id)}).mappings().first()
                if row:
                    if row["kind"] == "withdrawal":
                        current_balance = user_balance(row["user_id"])
                        if Decimal(str(row["amount"])) > current_balance:
                            st.error("Balance haitoshi; withdrawal haijaidhinishwa.")
                        else:
                            conn.execute(text("UPDATE transactions SET status='approved', reviewed_by=:admin WHERE id=:id"),
                                         {"admin": user["username"], "id": int(tx_id)})
                            st.success("Transaction approved.")
                            st.rerun()
                    else:
                        conn.execute(text("UPDATE transactions SET status='approved', reviewed_by=:admin WHERE id=:id"),
                                     {"admin": user["username"], "id": int(tx_id)})
                        st.rerun()
                else:
                    st.error("Pending transaction haijapatikana.")
        if y.button("Reject transaction"):
            with get_engine().begin() as conn:
                conn.execute(text("UPDATE transactions SET status='rejected', reviewed_by=:admin WHERE id=:id AND status='pending'"),
                             {"admin": user["username"], "id": int(tx_id)})
            st.rerun()

elif page == "Help":
    st.title("Help & Support")
    st.write("Get intouch With Mkondo Home Technology Cistomer services center For more Assistance," \
    " Chalenges,Questions and Problems Through phone number +255764460942.")
