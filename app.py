import os
import sqlite3
from functools import wraps
from datetime import datetime

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    session,
    flash,
    render_template_string,
    g,
    jsonify,
)

# Optional OpenAI integration
OPENAI_ENABLED = True
try:
    from openai import OpenAI
except Exception:
    OPENAI_ENABLED = False


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
DATABASE = "propertyhub.db"


# ---------------------------
# Database helpers
# ---------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner', 'tenant')),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            rent INTEGER NOT NULL,
            beds INTEGER NOT NULL,
            baths REAL NOT NULL,
            sqft INTEGER NOT NULL,
            description TEXT NOT NULL,
            owner_id INTEGER,
            status TEXT NOT NULL DEFAULT 'available',
            image_url TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            tenant_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY(property_id) REFERENCES properties(id),
            FOREIGN KEY(tenant_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            property_id INTEGER,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(recipient_id) REFERENCES users(id),
            FOREIGN KEY(property_id) REFERENCES properties(id)
        );

        CREATE TABLE IF NOT EXISTS maintenance_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            property_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            FOREIGN KEY(tenant_id) REFERENCES users(id),
            FOREIGN KEY(owner_id) REFERENCES users(id),
            FOREIGN KEY(property_id) REFERENCES properties(id)
        );

        CREATE TABLE IF NOT EXISTS leases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            tenant_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            monthly_rent INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            FOREIGN KEY(property_id) REFERENCES properties(id),
            FOREIGN KEY(tenant_id) REFERENCES users(id),
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lease_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'due',
            created_at TEXT NOT NULL,
            FOREIGN KEY(lease_id) REFERENCES leases(id)
        );
        """
    )

    db.commit()
    seed_data()


def seed_data():
    db = get_db()

    user_count = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if user_count > 0:
        return

    now = datetime.utcnow().isoformat()

    # Demo users
    db.execute(
        "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Owner Demo", "owner@propertyhub.com", "demo123", "owner", now),
    )
    db.execute(
        "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Tenant Demo", "tenant@propertyhub.com", "demo123", "tenant", now),
    )

    owner_id = db.execute(
        "SELECT id FROM users WHERE email = ?",
        ("owner@propertyhub.com",)
    ).fetchone()["id"]

    # Demo properties
    properties = [
        (
            "Modern 2BR Apartment",
            "1208 Main Street",
            "Dallas",
            "TX",
            "75201",
            1850,
            2,
            2.0,
            1020,
            "Clean modern unit with quartz counters, stainless appliances, balcony, and great natural light.",
            owner_id,
            "available",
            "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?q=80&w=1200&auto=format&fit=crop",
            now
        ),
        (
            "Luxury 1BR Uptown Loft",
            "300 Cedar Avenue",
            "Dallas",
            "TX",
            "75204",
            1595,
            1,
            1.0,
            815,
            "Open-concept loft with premium finishes, rooftop access, and secure parking.",
            owner_id,
            "available",
            "https://images.unsplash.com/photo-1494526585095-c41746248156?q=80&w=1200&auto=format&fit=crop",
            now
        ),
        (
            "Renovated Family Home",
            "44 Magnolia Drive",
            "Biloxi",
            "MS",
            "39532",
            2550,
            3,
            2.0,
            1890,
            "Fresh renovation with light oak floors, white cabinets, quartz counters, and fenced backyard.",
            owner_id,
            "available",
            "https://images.unsplash.com/photo-1568605114967-8130f3a36994?q=80&w=1200&auto=format&fit=crop",
            now
        ),
    ]

    db.executemany(
        """
        INSERT INTO properties
        (title, address, city, state, zip_code, rent, beds, baths, sqft, description, owner_id, status, image_url, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        properties,
    )

    tenant_id = db.execute(
        "SELECT id FROM users WHERE email = ?",
        ("tenant@propertyhub.com",)
    ).fetchone()["id"]

    property_id = db.execute(
        "SELECT id FROM properties WHERE title = ?",
        ("Modern 2BR Apartment",)
    ).fetchone()["id"]

    db.execute(
        """
        INSERT INTO leases (property_id, tenant_id, owner_id, start_date, end_date, monthly_rent, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (property_id, tenant_id, owner_id, "2026-04-01", "2027-03-31", 1850, "active", now),
    )

    lease_id = db.execute(
        "SELECT id FROM leases WHERE tenant_id = ? LIMIT 1",
        (tenant_id,)
    ).fetchone()["id"]

    db.execute(
        """
        INSERT INTO payments (lease_id, amount, due_date, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (lease_id, 1850, "2026-05-01", "due", now),
    )

    db.commit()


# ---------------------------
# Auth helpers
# ---------------------------
def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            if user["role"] != role:
                flash("Access denied.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------
# Base template
# ---------------------------
BASE_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title or "PropertyHub" }}</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f5f7fb;
            color: #111827;
        }
        a { text-decoration: none; color: inherit; }
        .nav {
            background: #0f172a;
            color: white;
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .nav-links a {
            margin-left: 16px;
            color: #e5e7eb;
        }
        .nav-links a:hover { color: white; }
        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 24px;
        }
        .hero {
            background: linear-gradient(135deg, #0f172a, #1d4ed8);
            color: white;
            padding: 64px 24px;
            border-radius: 20px;
            margin-bottom: 28px;
        }
        .hero h1 {
            font-size: 44px;
            margin: 0 0 12px;
        }
        .hero p {
            font-size: 18px;
            max-width: 700px;
            color: #dbeafe;
        }
        .btn {
            display: inline-block;
            padding: 12px 18px;
            border-radius: 10px;
            background: #2563eb;
            color: white;
            border: none;
            cursor: pointer;
            font-weight: bold;
        }
        .btn.secondary { background: #111827; }
        .btn.light { background: white; color: #111827; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
        }
        .property-img {
            width: 100%;
            height: 190px;
            object-fit: cover;
            border-radius: 12px;
            margin-bottom: 12px;
        }
        .muted { color: #6b7280; }
        .badge {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            background: #e0e7ff;
            color: #3730a3;
            font-size: 12px;
            font-weight: bold;
        }
        .section-title {
            font-size: 26px;
            margin-bottom: 16px;
        }
        form {
            display: grid;
            gap: 12px;
        }
        input, select, textarea {
            width: 100%;
            padding: 12px;
            border-radius: 10px;
            border: 1px solid #d1d5db;
            font-size: 14px;
        }
        textarea { min-height: 120px; resize: vertical; }
        .row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
        }
        .table-wrap {
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 12px;
            overflow: hidden;
        }
        th, td {
            text-align: left;
            padding: 14px;
            border-bottom: 1px solid #e5e7eb;
            vertical-align: top;
        }
        th {
            background: #f8fafc;
        }
        .flash {
            padding: 12px 14px;
            border-radius: 10px;
            margin-bottom: 16px;
        }
        .flash-success { background: #dcfce7; color: #166534; }
        .flash-danger { background: #fee2e2; color: #991b1b; }
        .flash-warning { background: #fef3c7; color: #92400e; }
        .flash-info { background: #dbeafe; color: #1d4ed8; }
        .footer {
            text-align: center;
            color: #6b7280;
            padding: 24px;
        }
        .chat-box {
            background: #ffffff;
            border-radius: 16px;
            padding: 18px;
            min-height: 220px;
            border: 1px solid #e5e7eb;
            white-space: pre-wrap;
        }
        @media (max-width: 720px) {
            .hero h1 { font-size: 34px; }
            .row { grid-template-columns: 1fr; }
            .nav { flex-direction: column; gap: 10px; align-items: flex-start; }
            .nav-links a { margin-left: 0; margin-right: 12px; }
        }
    </style>
</head>
<body>
    <div class="nav">
        <div><a href="{{ url_for('home') }}"><strong>PropertyHub</strong></a></div>
        <div class="nav-links">
            <a href="{{ url_for('list_properties') }}">Properties</a>
            {% if user %}
                <a href="{{ url_for('dashboard') }}">Dashboard</a>
                <a href="{{ url_for('ai_assistant') }}">AI Assistant</a>
                <a href="{{ url_for('logout') }}">Logout</a>
            {% else %}
                <a href="{{ url_for('login') }}">Login</a>
                <a href="{{
