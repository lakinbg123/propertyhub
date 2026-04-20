import os
import sqlite3
from functools import wraps
from datetime import datetime

from flask import Flask, request, redirect, url_for, session, flash, render_template_string, g, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DATABASE = "propertyhub.db"

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False


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


def current_time():
    return datetime.utcnow().isoformat()


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
            image_url TEXT,
            status TEXT NOT NULL DEFAULT 'available',
            owner_id INTEGER,
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
    seed_demo_data()


def seed_demo_data():
    db = get_db()
    count = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    if count:
        return

    db.execute(
        "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Owner Demo", "owner@propertyhub.com", "demo123", "owner", current_time()),
    )
    db.execute(
        "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Tenant Demo", "tenant@propertyhub.com", "demo123", "tenant", current_time()),
    )
    owner_id = db.execute("SELECT id FROM users WHERE email=?", ("owner@propertyhub.com",)).fetchone()["id"]
    tenant_id = db.execute("SELECT id FROM users WHERE email=?", ("tenant@propertyhub.com",)).fetchone()["id"]

    demo_properties = [
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
            "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?q=80&w=1200&auto=format&fit=crop",
            "available",
            owner_id,
            current_time(),
        ),
        (
            "Luxury 1BR Loft",
            "300 Cedar Avenue",
            "Dallas",
            "TX",
            "75204",
            1595,
            1,
            1.0,
            815,
            "Open-concept loft with premium finishes, rooftop access, secure parking, and downtown access.",
            "https://images.unsplash.com/photo-1494526585095-c41746248156?q=80&w=1200&auto=format&fit=crop",
            "available",
            owner_id,
            current_time(),
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
            "https://images.unsplash.com/photo-1568605114967-8130f3a36994?q=80&w=1200&auto=format&fit=crop",
            "available",
            owner_id,
            current_time(),
        ),
    ]

    db.executemany(
        """
        INSERT INTO properties
        (title,address,city,state,zip_code,rent,beds,baths,sqft,description,image_url,status,owner_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        demo_properties,
    )

    property_id = db.execute("SELECT id FROM properties ORDER BY id LIMIT 1").fetchone()["id"]
    db.execute(
        """
        INSERT INTO leases (property_id, tenant_id, owner_id, start_date, end_date, monthly_rent, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (property_id, tenant_id, owner_id, "2026-04-01", "2027-03-31", 1850, "active", current_time()),
    )
    lease_id = db.execute("SELECT id FROM leases LIMIT 1").fetchone()["id"]
    db.execute(
        "INSERT INTO payments (lease_id, amount, due_date, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (lease_id, 1850, "2026-05-01", "due", current_time()),
    )
    db.commit()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped


def role_required(role):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            if user["role"] != role:
                flash("Access denied.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapped
    return decorator


BASE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title or 'PropertyHub' }}</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Arial, sans-serif; background: #f5f7fb; color: #111827; }
    a { color: inherit; text-decoration: none; }
    .nav { background:#0f172a; color:white; padding:16px 24px; display:flex; justify-content:space-between; align-items:center; gap:16px; }
    .nav-links a { margin-left:16px; color:#e5e7eb; }
    .nav-links a:hover { color:white; }
    .container { max-width: 1120px; margin: 0 auto; padding: 24px; }
    .hero { background: linear-gradient(135deg,#0f172a,#1d4ed8); color:white; padding:56px 28px; border-radius:20px; margin-bottom:28px; }
    .hero h1 { margin:0 0 12px; font-size:42px; }
    .hero p { color:#dbeafe; font-size:18px; max-width:760px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:20px; }
    .card { background:white; border-radius:16px; padding:18px; box-shadow:0 8px 24px rgba(15,23,42,.08); }
    .property-img { width:100%; height:190px; object-fit:cover; border-radius:12px; margin-bottom:12px; }
    .btn { display:inline-block; padding:12px 18px; border-radius:10px; background:#2563eb; color:white; border:none; cursor:pointer; font-weight:700; }
    .btn.secondary { background:#111827; }
    .btn.light { background:white; color:#111827; }
    .badge { display:inline-block; padding:6px 10px; border-radius:999px; background:#e0e7ff; color:#3730a3; font-size:12px; font-weight:700; }
    .muted { color:#6b7280; }
    .section-title { font-size:26px; margin-bottom:16px; }
    input, select, textarea { width:100%; padding:12px; border-radius:10px; border:1px solid #d1d5db; font-size:14px; }
    textarea { min-height:120px; resize:vertical; }
    form { display:grid; gap:12px; }
    .row { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
    .flash { padding:12px 14px; border-radius:10px; margin-bottom:16px; }
    .flash-success { background:#dcfce7; color:#166534; }
    .flash-danger { background:#fee2e2; color:#991b1b; }
    .flash-warning { background:#fef3c7; color:#92400e; }
    .flash-info { background:#dbeafe; color:#1d4ed8; }
    table { width:100%; border-collapse:collapse; background:white; border-radius:12px; overflow:hidden; }
    th, td { text-align:left; padding:14px; border-bottom:1px solid #e5e7eb; vertical-align:top; }
    th { background:#f8fafc; }
    .table-wrap { overflow-x:auto; }
    .footer { text-align:center; color:#6b7280; padding:24px; }
    .chat-box { background:#fff; border-radius:16px; padding:18px; min-height:220px; border:1px solid #e5e7eb; white-space:pre-wrap; }
    @media (max-width: 720px) {
      .nav { flex-direction:column; align-items:flex-start; }
      .nav-links a { margin-left:0; margin-right:12px; }
      .row { grid-template-columns:1fr; }
      .hero h1 { font-size:34px; }
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
        <a href="{{ url_for('inbox') }}">Messages</a>
        <a href="{{ url_for('ai_assistant') }}">AI Assistant</a>
        <a href="{{ url_for('logout') }}">Logout</a>
      {% else %}
        <a href="{{ url_for('login') }}">Login</a>
        <a href="{{ url_for('signup') }}">Sign Up</a>
      {% endif %}
    </div>
  </div>

  <div class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="flash flash-{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {{ content|safe }}
  </div>

  <div class="footer">PropertyHub demo platform</div>
</body>
</html>
"""


def render_page(content, title="PropertyHub"):
    return render_template_string(BASE_HTML, content=content, title=title, user=current_user())


@app.route("/")
def home():
    db = get_db()
    featured = db.execute("SELECT * FROM properties ORDER BY id DESC LIMIT 3").fetchall()
    cards = ""
    for p in featured:
        cards += f"""
        <div class='card'>
          <img class='property-img' src='{p['image_url']}' alt='{p['title']}'>
          <div class='badge'>{p['status'].title()}</div>
          <h3>{p['title']}</h3>
          <p class='muted'>{p['address']}, {p['city']}, {p['state']} {p['zip_code']}</p>
          <p><strong>${p['rent']:,}/mo</strong> Â· {p['beds']} bd Â· {p['baths']} ba Â· {p['sqft']} sqft</p>
          <p>{p['description']}</p>
          <a class='btn' href='{url_for('property_detail', property_id=p['id'])}'>View Property</a>
        </div>
        """

    content = f"""
    <div class='hero'>
      <h1>Modern Property Management, Without the Mess</h1>
      <p>List rentals, handle applications, track maintenance, message tenants, and centralize everything in one clean dashboard.</p>
      <div style='margin-top:20px;'>
        <a class='btn light' href='{url_for('list_properties')}'>Browse Properties</a>
        <a class='btn secondary' style='margin-left:10px;' href='{url_for('signup')}'>Create Account</a>
      </div>
    </div>
    <h2 class='section-title'>Featured Properties</h2>
    <div class='grid'>{cards}</div>
    """
    return render_page(content, "PropertyHub Home")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip()
        if not all([name, email, password, role]):
            flash("Please fill out all fields.", "danger")
            return redirect(url_for("signup"))
        try:
            get_db().execute(
                "INSERT INTO users (name,email,password,role,created_at) VALUES (?,?,?,?,?)",
                (name, email, password, role, current_time()),
            )
            get_db().commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already in use.", "danger")
            return redirect(url_for("signup"))

    content = """
    <div class='card' style='max-width:600px;margin:0 auto;'>
      <h2>Create Account</h2>
      <form method='POST'>
        <input name='name' placeholder='Full name' required>
        <input name='email' type='email' placeholder='Email' required>
        <input name='password' type='password' placeholder='Password' required>
        <select name='role' required>
          <option value=''>Choose role</option>
          <option value='owner'>Owner / Property Manager</option>
          <option value='tenant'>Tenant</option>
        </select>
        <button class='btn' type='submit'>Create Account</button>
      </form>
      <p class='muted' style='margin-top:12px;'>Demo owner: owner@propertyhub.com / demo123</p>
      <p class='muted'>Demo tenant: tenant@propertyhub.com / demo123</p>
    </div>
    """
    return render_page(content, "Sign Up")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        user = get_db().execute(
            "SELECT * FROM users WHERE email = ? AND password = ?",
            (email, password),
        ).fetchone()
        if not user:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))
        session["user_id"] = user["id"]
        flash("Logged in successfully.", "success")
        return redirect(url_for("dashboard"))

    content = """
    <div class='card' style='max-width:520px;margin:0 auto;'>
      <h2>Login</h2>
      <form method='POST'>
        <input name='email' type='email' placeholder='Email' required>
        <input name='password' type='password' placeholder='Password' required>
        <button class='btn' type='submit'>Login</button>
      </form>
      <p class='muted' style='margin-top:12px;'>Demo owner: owner@propertyhub.com / demo123</p>
      <p class='muted'>Demo tenant: tenant@propertyhub.com / demo123</p>
    </div>
    """
    return render_page(content, "Login")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("home"))


@app.route("/properties")
def list_properties():
    rows = get_db().execute(
        """
        SELECT p.*, u.name owner_name
        FROM properties p
        LEFT JOIN users u ON p.owner_id = u.id
        ORDER BY p.id DESC
        """
    ).fetchall()
    cards = ""
    for p in rows:
        cards += f"""
        <div class='card'>
          <img class='property-img' src='{p['image_url']}' alt='{p['title']}'>
          <div class='badge'>{p['status'].title()}</div>
          <h3>{p['title']}</h3>
          <p class='muted'>{p['address']}, {p['city']}, {p['state']} {p['zip_code']}</p>
          <p><strong>${p['rent']:,}/mo</strong> Â· {p['beds']} bd Â· {p['baths']} ba Â· {p['sqft']} sqft</p>
          <p>{p['description']}</p>
          <p class='muted'>Listed by: {p['owner_name'] or 'PropertyHub'}</p>
          <a class='btn' href='{url_for('property_detail', property_id=p['id'])}'>View Details</a>
        </div>
        """
    return render_page(f"<h2 class='section-title'>Available Properties</h2><div class='grid'>{cards}</div>", "Properties")


@app.route("/properties/<int:property_id>", methods=["GET", "POST"])
def property_detail(property_id):
    db = get_db()
    p = db.execute(
        """
        SELECT p.*, u.name owner_name, u.id owner_id
        FROM properties p
        LEFT JOIN users u ON p.owner_id = u.id
        WHERE p.id = ?
        """,
        (property_id,),
    ).fetchone()
    if not p:
        flash("Property not found.", "danger")
        return redirect(url_for("list_properties"))

    user = current_user()
    if request.method == "POST":
        if not user or user["role"] != "tenant":
            flash("Log in as a tenant to apply.", "warning")
            return redirect(url_for("login"))
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        notes = request.form.get("notes", "").strip()
        db.execute(
            "INSERT INTO applications (property_id, tenant_id, full_name, phone, notes, status, created_at) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (property_id, user["id"], full_name, phone, notes, current_time()),
        )
        db.execute(
            "INSERT INTO messages (sender_id, recipient_id, property_id, subject, body, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                user["id"],
                p["owner_id"],
                property_id,
                f"New application for {p['title']}",
                f"{full_name} submitted an application. Phone: {phone}. Notes: {notes}",
                current_time(),
            ),
        )
        db.commit()
        flash("Application submitted successfully.", "success")
        return redirect(url_for("property_detail", property_id=property_id))

    if user and user["role"] == "tenant":
        apply_form = """
        <div class='card' style='margin-top:20px;'>
          <h3>Apply for this Property</h3>
          <form method='POST'>
            <input name='full_name' placeholder='Full name' required>
            <input name='phone' placeholder='Phone number' required>
            <textarea name='notes' placeholder='Tell us a little about yourself'></textarea>
            <button class='btn' type='submit'>Submit Application</button>
          </form>
        </div>
        """
    else:
        apply_form = f"""
        <div class='card' style='margin-top:20px;'>
          <h3>Interested in this property?</h3>
          <p class='muted'>Log in as a tenant to apply online.</p>
          <a class='btn' href='{url_for('login')}'>Login to Apply</a>
        </div>
        """

    content = f"""
    <div class='card'>
      <img class='property-img' style='height:340px;' src='{p['image_url']}' alt='{p['title']}'>
      <div class='badge'>{p['status'].title()}</div>
      <h2>{p['title']}</h2>
      <p class='muted'>{p['address']}, {p['city']}, {p['state']} {p['zip_code']}</p>
      <p><strong>${p['rent']:,}/month</strong></p>
      <p>{p['beds']} bedrooms Â· {p['baths']} bathrooms Â· {p['sqft']} sqft</p>
      <p>{p['description']}</p>
      <p class='muted'>Managed by: {p['owner_name'] or 'PropertyHub'}</p>
    </div>
    {apply_form}
    """
    return render_page(content, p["title"])


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    db = get_db()

    if user["role"] == "owner":
        properties_count = db.execute("SELECT COUNT(*) c FROM properties WHERE owner_id = ?", (user["id"],)).fetchone()["c"]
        apps_count = db.execute(
            "SELECT COUNT(*) c FROM applications a JOIN properties p ON a.property_id = p.id WHERE p.owner_id = ?",
            (user["id"],),
        ).fetchone()["c"]
        maintenance_count = db.execute(
            "SELECT COUNT(*) c FROM maintenance_requests WHERE owner_id = ? AND status = 'open'",
            (user["id"],),
        ).fetchone()["c"]
        messages = db.execute(
            "SELECT COUNT(*) c FROM messages WHERE recipient_id = ?",
            (user["id"],),
        ).fetchone()["c"]

        applications = db.execute(
            """
            SELECT a.*, p.title property_title
            FROM applications a
            JOIN properties p ON a.property_id = p.id
            WHERE p.owner_id = ?
            ORDER BY a.id DESC
            LIMIT 8
            """,
            (user["id"],),
        ).fetchall()

        app_rows = "".join(
            f"<tr><td>{a['full_name']}</td><td>{a['property_title']}</td><td>{a['phone']}</td><td>{a['status']}</td></tr>"
            for a in applications
        ) or "<tr><td colspan='4'>No applications yet.</td></tr>"

        content = f"""
        <h2 class='section-title'>Owner Dashboard</h2>
        <div class='grid'>
          <div class='card'><h3>{properties_count}</h3><p class='muted'>Properties</p></div>
          <div class='card'><h3>{apps_count}</h3><p class='muted'>Applications</p></div>
          <div class='card'><h3>{maintenance_count}</h3><p class='muted'>Open Maintenance Requests</p></div>
          <div class='card'><h3>{messages}</h3><p class='muted'>Messages</p></div>
        </div>

        <div class='card' style='margin-top:22px;'>
          <h3>Add Property</h3>
          <form method='POST' action='{url_for('add_property')}'>
            <div class='row'>
              <input name='title' placeholder='Title' required>
              <input name='rent' placeholder='Monthly rent' type='number' required>
            </div>
            <div class='row'>
              <input name='address' placeholder='Address' required>
              <input name='city' placeholder='City' required>
            </div>
            <div class='row'>
              <input name='state' placeholder='State' required>
              <input name='zip_code' placeholder='ZIP code' required>
            </div>
            <div class='row'>
              <input name='beds' placeholder='Beds' type='number' required>
              <input name='baths' placeholder='Baths' step='0.5' type='number' required>
            </div>
            <div class='row'>
              <input name='sqft' placeholder='Square feet' type='number' required>
              <input name='image_url' placeholder='Image URL'>
            </div>
            <textarea name='description' placeholder='Description' required></textarea>
            <button class='btn' type='submit'>Add Property</button>
          </form>
        </div>

        <div class='card' style='margin-top:22px;'>
          <h3>Recent Applications</h3>
          <div class='table-wrap'>
            <table>
              <thead><tr><th>Name</th><th>Property</th><th>Phone</th><th>Status</th></tr></thead>
              <tbody>{app_rows}</tbody>
            </table>
          </div>
        </div>
        """
        return render_page(content, "Owner Dashboard")

    lease = db.execute(
        """
        SELECT l.*, p.title property_title, p.address
        FROM leases l
        JOIN properties p ON l.property_id = p.id
        WHERE l.tenant_id = ? AND l.status = 'active'
        ORDER BY l.id DESC LIMIT 1
        """,
        (user["id"],),
    ).fetchone()
    payments = db.execute(
        """
        SELECT pay.*
        FROM payments pay
        JOIN leases l ON pay.lease_id = l.id
        WHERE l.tenant_id = ?
        ORDER BY pay.id DESC
        LIMIT 8
        """,
        (user["id"],),
    ).fetchall()
    payment_rows = "".join(
        f"<tr><td>${p['amount']:,}</td><td>{p['due_date']}</td><td>{p['status']}</td></tr>"
        for p in payments
    ) or "<tr><td colspan='3'>No payment records yet.</td></tr>"

    lease_box = (
        f"<div class='card'><h3>Current Lease</h3><p><strong>{lease['property_title']}</strong></p><p class='muted'>{lease['address']}</p><p>${lease['monthly_rent']:,}/month</p><p>{lease['start_date']} to {lease['end_date']}</p></div>"
        if lease else
        "<div class='card'><h3>No Active Lease</h3><p class='muted'>You are not assigned to a lease yet.</p></div>"
    )

    property_options = db.execute("SELECT id, title FROM properties ORDER BY id DESC").fetchall()
    options_html = "".join(f"<option value='{p['id']}'>{p['title']}</option>" for p in property_options)

    content = f"""
    <h2 class='section-title'>Tenant Dashboard</h2>
    <div class='grid'>
      {lease_box}
      <div class='card'>
        <h3>Submit Maintenance Request</h3>
        <form method='POST' action='{url_for('create_maintenance')}'>
          <select name='property_id' required>
            <option value=''>Choose property</option>
            {options_html}
          </select>
          <input name='title' placeholder='Issue title' required>
          <select name='priority' required>
            <option value='low'>Low</option>
            <option value='medium' selected>Medium</option>
            <option value='high'>High</option>
          </select>
          <textarea name='description' placeholder='Describe the issue' required></textarea>
          <button class='btn' type='submit'>Submit Request</button>
        </form>
      </div>
    </div>

    <div class='card' style='margin-top:22px;'>
      <h3>Payment Tracking</h3>
      <div class='table-wrap'>
        <table>
          <thead><tr><th>Amount</th><th>Due Date</th><th>Status</th></tr></thead>
          <tbody>{payment_rows}</tbody>
        </table>
      </div>
    </div>
    """
    return render_page(content, "Tenant Dashboard")


@app.route("/owner/add-property", methods=["POST"])
@login_required
@role_required("owner")
def add_property():
    user = current_user()
    form = request.form
    image_url = form.get("image_url", "").strip() or "https://images.unsplash.com/photo-1560185007-c5ca9d2c014d?q=80&w=1200&auto=format&fit=crop"
    get_db().execute(
        """
        INSERT INTO properties
        (title,address,city,state,zip_code,rent,beds,baths,sqft,description,image_url,status,owner_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            form.get("title", "").strip(),
            form.get("address", "").strip(),
            form.get("city", "").strip(),
            form.get("state", "").strip(),
            form.get("zip_code", "").strip(),
            int(form.get("rent", 0)),
            int(form.get("beds", 0)),
            float(form.get("baths", 0)),
            int(form.get("sqft", 0)),
            form.get("description", "").strip(),
            image_url,
            "available",
            user["id"],
            current_time(),
        ),
    )
    get_db().commit()
    flash("Property added successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/messages")
@login_required
def inbox():
    db = get_db()
    user = current_user()
    rows = db.execute(
        """
        SELECT m.*, s.name sender_name, r.name recipient_name, p.title property_title
        FROM messages m
        JOIN users s ON m.sender_id = s.id
        JOIN users r ON m.recipient_id = r.id
        LEFT JOIN properties p ON m.property_id = p.id
        WHERE m.sender_id = ? OR m.recipient_id = ?
        ORDER BY m.id DESC
        """,
        (user["id"], user["id"]),
    ).fetchall()

    message_cards = ""
    for m in rows:
        property_line = f"<p class='muted'>Property: {m['property_title']}</p>" if m['property_title'] else ""
        message_cards += f"""
        <div class='card'>
          <h3>{m['subject']}</h3>
          <p class='muted'>From: {m['sender_name']} Â· To: {m['recipient_name']} Â· {m['created_at'][:16].replace('T', ' ')}</p>
          {property_line}
          <p>{m['body']}</p>
        </div>
        """
    if not message_cards:
        message_cards = "<div class='card'><p class='muted'>No messages yet.</p></div>"

    recipients = db.execute("SELECT id, name, role FROM users WHERE id != ? ORDER BY name", (user["id"],)).fetchall()
    recipient_options = "".join(f"<option value='{r['id']}'>{r['name']} ({r['role']})</option>" for r in recipients)
    properties = db.execute("SELECT id, title FROM properties ORDER BY id DESC").fetchall()
    property_options = "<option value=''>No property linked</option>" + "".join(f"<option value='{p['id']}'>{p['title']}</option>" for p in properties)

    content = f"""
    <h2 class='section-title'>Messages</h2>
    <div class='card' style='margin-bottom:22px;'>
      <h3>Send Message</h3>
      <form method='POST' action='{url_for('send_message')}'>
        <div class='row'>
          <select name='recipient_id' required>{recipient_options}</select>
          <select name='property_id'>{property_options}</select>
        </div>
        <input name='subject' placeholder='Subject' required>
        <textarea name='body' placeholder='Write your message' required></textarea>
        <button class='btn' type='submit'>Send</button>
      </form>
    </div>
    <div class='grid'>{message_cards}</div>
    """
    return render_page(content, "Messages")


@app.route("/messages/send", methods=["POST"])
@login_required
def send_message():
    db = get_db()
    db.execute(
        "INSERT INTO messages (sender_id, recipient_id, property_id, subject, body, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            current_user()["id"],
            int(request.form.get("recipient_id")),
            int(request.form.get("property_id")) if request.form.get("property_id") else None,
            request.form.get("subject", "").strip(),
            request.form.get("body", "").strip(),
            current_time(),
        ),
    )
    db.commit()
    flash("Message sent.", "success")
    return redirect(url_for("inbox"))


@app.route("/maintenance/create", methods=["POST"])
@login_required
@role_required("tenant")
def create_maintenance():
    db = get_db()
    property_id = int(request.form.get("property_id"))
    prop = db.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    if not prop:
        flash("Property not found.", "danger")
        return redirect(url_for("dashboard"))
    db.execute(
        "INSERT INTO maintenance_requests (tenant_id, owner_id, property_id, title, description, priority, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'open', ?)",
        (
            current_user()["id"],
            prop["owner_id"],
            property_id,
            request.form.get("title", "").strip(),
            request.form.get("description", "").strip(),
            request.form.get("priority", "medium"),
            current_time(),
        ),
    )
    db.commit()
    flash("Maintenance request submitted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/ai-assistant", methods=["GET", "POST"])
@login_required
def ai_assistant():
    answer = "Ask about lease reminders, tenant replies, listing descriptions, or maintenance messages."
    if request.method == "POST":
        prompt = request.form.get("prompt", "").strip()
        if not OPENAI_AVAILABLE:
            answer = "The openai package is not installed yet. Add it to requirements.txt and redeploy."
        elif not os.environ.get("OPENAI_API_KEY"):
            answer = "OPENAI_API_KEY is not set in Render environment variables yet."
        elif not prompt:
            answer = "Enter a prompt first."
        else:
            try:
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                response = client.responses.create(
                    model="gpt-4.1-mini",
                    input=f"You are helping manage a property platform. Keep answers concise and useful. User request: {prompt}",
                )
                answer = getattr(response, "output_text", "No response returned.")
            except Exception as e:
                answer = f"AI request failed: {e}"

    content = f"""
    <h2 class='section-title'>AI Assistant</h2>
    <div class='card'>
      <form method='POST'>
        <textarea name='prompt' placeholder='Example: Write a professional reply to a tenant asking for late rent flexibility.' required></textarea>
        <button class='btn' type='submit'>Ask AI</button>
      </form>
    </div>
    <div class='card' style='margin-top:22px;'>
      <h3>Response</h3>
      <div class='chat-box'>{answer}</div>
    </div>
    """
    return render_page(content, "AI Assistant")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
