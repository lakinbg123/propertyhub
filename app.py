import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key')
DATABASE = os.environ.get('DATABASE_PATH', 'propertyhub.db')


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec='seconds')


def format_dt(value: str | None) -> str:
    if not value:
        return ''
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime('%b %d, %Y • %I:%M %p').replace(' 0', ' ')
    except ValueError:
        return value


app.jinja_env.filters['datetime'] = format_dt


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return get_db().execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def role_required(role: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                flash('Please log in first.', 'warning')
                return redirect(url_for('login'))
            if user['role'] != role:
                flash('Access denied.', 'danger')
                return redirect(url_for('dashboard'))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def init_db():
    db = get_db()
    db.executescript(
        '''
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

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            tenant_id INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(property_id) REFERENCES properties(id),
            FOREIGN KEY(owner_id) REFERENCES users(id),
            FOREIGN KEY(tenant_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id),
            FOREIGN KEY(sender_id) REFERENCES users(id)
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
            payment_method TEXT,
            card_last4 TEXT,
            created_at TEXT NOT NULL,
            paid_at TEXT,
            FOREIGN KEY(lease_id) REFERENCES leases(id)
        );
        '''
    )
    db.commit()
    seed_demo_data()


def seed_demo_data():
    db = get_db()
    existing = db.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
    if existing:
        return

    now = now_iso()
    db.execute(
        'INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)',
        ('Owner Demo', 'owner@propertyhub.com', 'demo123', 'owner', now),
    )
    db.execute(
        'INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)',
        ('Tenant Demo', 'tenant@propertyhub.com', 'demo123', 'tenant', now),
    )

    owner_id = db.execute('SELECT id FROM users WHERE email=?', ('owner@propertyhub.com',)).fetchone()['id']
    tenant_id = db.execute('SELECT id FROM users WHERE email=?', ('tenant@propertyhub.com',)).fetchone()['id']

    properties = [
        (
            'Modern 2BR Apartment', '1208 Main Street', 'Dallas', 'TX', '75201', 1850, 2, 2.0, 1020,
            'Clean modern unit with quartz counters, stainless appliances, balcony, and strong natural light.',
            'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?q=80&w=1400&auto=format&fit=crop',
            'available', owner_id, now,
        ),
        (
            'Luxury 1BR Loft', '300 Cedar Avenue', 'Dallas', 'TX', '75204', 1595, 1, 1.0, 815,
            'Open-concept loft with premium finishes, rooftop access, and secure parking.',
            'https://images.unsplash.com/photo-1494526585095-c41746248156?q=80&w=1400&auto=format&fit=crop',
            'available', owner_id, now,
        ),
        (
            'Renovated Family Home', '44 Magnolia Drive', 'Biloxi', 'MS', '39532', 2550, 3, 2.0, 1890,
            'Fresh renovation with light oak floors, white cabinets, quartz counters, and fenced backyard.',
            'https://images.unsplash.com/photo-1568605114967-8130f3a36994?q=80&w=1400&auto=format&fit=crop',
            'available', owner_id, now,
        ),
    ]

    db.executemany(
        '''
        INSERT INTO properties
        (title, address, city, state, zip_code, rent, beds, baths, sqft, description, image_url, status, owner_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        properties,
    )

    property_id = db.execute('SELECT id FROM properties ORDER BY id LIMIT 1').fetchone()['id']
    db.execute(
        '''
        INSERT INTO applications (property_id, tenant_id, full_name, phone, notes, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (property_id, tenant_id, 'Tenant Demo', '(555) 555-0199', 'Self-employed, flexible move-in, solid references.', 'pending', now),
    )

    db.execute(
        '''
        INSERT INTO leases (property_id, tenant_id, owner_id, start_date, end_date, monthly_rent, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (property_id, tenant_id, owner_id, '2026-04-01', '2027-03-31', 1850, 'active', now),
    )
    lease_id = db.execute('SELECT id FROM leases ORDER BY id DESC LIMIT 1').fetchone()['id']

    for offset, status in [(0, 'paid'), (1, 'due'), (2, 'scheduled')]:
        due = (datetime(2026, 4, 1) + timedelta(days=30 * offset)).date().isoformat()
        paid_at = now if status == 'paid' else None
        db.execute(
            '''
            INSERT INTO payments (lease_id, amount, due_date, status, payment_method, card_last4, created_at, paid_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (lease_id, 1850, due, status, 'Card' if status == 'paid' else None, '4242' if status == 'paid' else None, now, paid_at),
        )

    db.execute(
        '''
        INSERT INTO maintenance_requests (tenant_id, owner_id, property_id, title, description, priority, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (tenant_id, owner_id, property_id, 'AC tune-up', 'Air is cool but not getting the apartment down fast enough in the afternoon.', 'medium', 'open', now),
    )

    db.execute(
        'INSERT INTO conversations (property_id, owner_id, tenant_id, updated_at) VALUES (?, ?, ?, ?)',
        (property_id, owner_id, tenant_id, now),
    )
    conversation_id = db.execute('SELECT id FROM conversations ORDER BY id DESC LIMIT 1').fetchone()['id']
    db.execute(
        'INSERT INTO messages (conversation_id, sender_id, body, created_at) VALUES (?, ?, ?, ?)',
        (conversation_id, tenant_id, 'Hey, I submitted my application and wanted to ask if pets are allowed.', now),
    )
    db.execute(
        'INSERT INTO messages (conversation_id, sender_id, body, created_at) VALUES (?, ?, ?, ?)',
        (conversation_id, owner_id, 'Yes—small pets are fine with a deposit. I can send over the full policy.', now),
    )
    db.commit()


def get_counts(user):
    db = get_db()
    counts = {}
    if user['role'] == 'owner':
        counts['properties'] = db.execute('SELECT COUNT(*) c FROM properties WHERE owner_id = ?', (user['id'],)).fetchone()['c']
        counts['applications'] = db.execute(
            '''SELECT COUNT(*) c FROM applications a JOIN properties p ON a.property_id = p.id WHERE p.owner_id = ?''',
            (user['id'],),
        ).fetchone()['c']
        counts['payments_due'] = db.execute(
            '''
            SELECT COUNT(*) c
            FROM payments pay
            JOIN leases l ON pay.lease_id = l.id
            WHERE l.owner_id = ? AND pay.status IN ('due', 'scheduled')
            ''',
            (user['id'],),
        ).fetchone()['c']
        counts['open_requests'] = db.execute(
            'SELECT COUNT(*) c FROM maintenance_requests WHERE owner_id = ? AND status != "closed"',
            (user['id'],),
        ).fetchone()['c']
    else:
        counts['applications'] = db.execute('SELECT COUNT(*) c FROM applications WHERE tenant_id = ?', (user['id'],)).fetchone()['c']
        counts['payments_due'] = db.execute(
            '''
            SELECT COUNT(*) c
            FROM payments pay
            JOIN leases l ON pay.lease_id = l.id
            WHERE l.tenant_id = ? AND pay.status IN ('due', 'scheduled')
            ''',
            (user['id'],),
        ).fetchone()['c']
        counts['messages'] = db.execute(
            'SELECT COUNT(*) c FROM conversations WHERE tenant_id = ?',
            (user['id'],),
        ).fetchone()['c']
        counts['open_requests'] = db.execute(
            'SELECT COUNT(*) c FROM maintenance_requests WHERE tenant_id = ? AND status != "closed"',
            (user['id'],),
        ).fetchone()['c']
    return counts


@app.context_processor
def inject_globals():
    return {'current_user': current_user()}


@app.route('/')
def home():
    db = get_db()
    featured = db.execute('SELECT * FROM properties ORDER BY id DESC LIMIT 3').fetchall()
    return render_template('home.html', featured=featured)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', '').strip()
        if not all([name, email, password, role]):
            flash('Please complete every field.', 'danger')
            return redirect(url_for('signup'))
        try:
            get_db().execute(
                'INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)',
                (name, email, password, role, now_iso()),
            )
            get_db().commit()
            flash('Account created. Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('That email is already in use.', 'danger')
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        user = get_db().execute(
            'SELECT * FROM users WHERE email = ? AND password = ?',
            (email, password),
        ).fetchone()
        if not user:
            flash('Invalid login.', 'danger')
            return redirect(url_for('login'))
        session['user_id'] = user['id']
        flash('Welcome back.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    user = current_user()
    counts = get_counts(user)

    if user['role'] == 'owner':
        properties = db.execute('SELECT * FROM properties WHERE owner_id = ? ORDER BY id DESC LIMIT 3', (user['id'],)).fetchall()
        applications = db.execute(
            '''
            SELECT a.*, p.title AS property_title
            FROM applications a
            JOIN properties p ON a.property_id = p.id
            WHERE p.owner_id = ?
            ORDER BY a.created_at DESC LIMIT 5
            ''',
            (user['id'],),
        ).fetchall()
        payments = db.execute(
            '''
            SELECT pay.*, p.title AS property_title, u.name AS tenant_name
            FROM payments pay
            JOIN leases l ON pay.lease_id = l.id
            JOIN properties p ON l.property_id = p.id
            JOIN users u ON l.tenant_id = u.id
            WHERE l.owner_id = ?
            ORDER BY pay.due_date ASC LIMIT 5
            ''',
            (user['id'],),
        ).fetchall()
        conversations = db.execute(
            '''
            SELECT c.*, p.title AS property_title, u.name AS other_name,
                   (SELECT body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) AS last_message
            FROM conversations c
            JOIN properties p ON c.property_id = p.id
            JOIN users u ON c.tenant_id = u.id
            WHERE c.owner_id = ?
            ORDER BY c.updated_at DESC LIMIT 5
            ''',
            (user['id'],),
        ).fetchall()
        return render_template('dashboard_owner.html', counts=counts, properties=properties, applications=applications, payments=payments, conversations=conversations)

    applications = db.execute(
        '''
        SELECT a.*, p.title AS property_title
        FROM applications a
        JOIN properties p ON a.property_id = p.id
        WHERE a.tenant_id = ?
        ORDER BY a.created_at DESC LIMIT 5
        ''',
        (user['id'],),
    ).fetchall()
    payments = db.execute(
        '''
        SELECT pay.*, p.title AS property_title
        FROM payments pay
        JOIN leases l ON pay.lease_id = l.id
        JOIN properties p ON l.property_id = p.id
        WHERE l.tenant_id = ?
        ORDER BY pay.due_date ASC LIMIT 5
        ''',
        (user['id'],),
    ).fetchall()
    conversations = db.execute(
        '''
        SELECT c.*, p.title AS property_title, u.name AS other_name,
               (SELECT body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) AS last_message
        FROM conversations c
        JOIN properties p ON c.property_id = p.id
        JOIN users u ON c.owner_id = u.id
        WHERE c.tenant_id = ?
        ORDER BY c.updated_at DESC LIMIT 5
        ''',
        (user['id'],),
    ).fetchall()
    requests_ = db.execute(
        'SELECT * FROM maintenance_requests WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 5',
        (user['id'],),
    ).fetchall()
    return render_template('dashboard_tenant.html', counts=counts, applications=applications, payments=payments, conversations=conversations, requests=requests_)


@app.route('/properties')
def properties():
    db = get_db()
    items = db.execute('SELECT p.*, u.name AS owner_name FROM properties p LEFT JOIN users u ON p.owner_id = u.id ORDER BY p.id DESC').fetchall()
    return render_template('properties.html', properties=items)


@app.route('/properties/<int:property_id>', methods=['GET', 'POST'])
def property_detail(property_id: int):
    db = get_db()
    property_row = db.execute(
        'SELECT p.*, u.name AS owner_name FROM properties p LEFT JOIN users u ON p.owner_id = u.id WHERE p.id = ?',
        (property_id,),
    ).fetchone()
    if not property_row:
        flash('Property not found.', 'danger')
        return redirect(url_for('properties'))

    user = current_user()
    if request.method == 'POST':
        if not user or user['role'] != 'tenant':
            flash('Log in as a tenant to apply.', 'warning')
            return redirect(url_for('login'))
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        notes = request.form.get('notes', '').strip()
        if not full_name or not phone:
            flash('Name and phone are required.', 'danger')
            return redirect(url_for('property_detail', property_id=property_id))
        db.execute(
            'INSERT INTO applications (property_id, tenant_id, full_name, phone, notes, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (property_id, user['id'], full_name, phone, notes, 'pending', now_iso()),
        )

        conv = db.execute(
            'SELECT id FROM conversations WHERE property_id = ? AND owner_id = ? AND tenant_id = ?',
            (property_id, property_row['owner_id'], user['id']),
        ).fetchone()
        if conv:
            conversation_id = conv['id']
            db.execute('UPDATE conversations SET updated_at = ? WHERE id = ?', (now_iso(), conversation_id))
        else:
            db.execute(
                'INSERT INTO conversations (property_id, owner_id, tenant_id, updated_at) VALUES (?, ?, ?, ?)',
                (property_id, property_row['owner_id'], user['id'], now_iso()),
            )
            conversation_id = db.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
        db.execute(
            'INSERT INTO messages (conversation_id, sender_id, body, created_at) VALUES (?, ?, ?, ?)',
            (conversation_id, user['id'], 'Hi, I just submitted an application and wanted to introduce myself.', now_iso()),
        )
        db.commit()
        flash('Application submitted.', 'success')
        return redirect(url_for('applications'))

    return render_template('property_detail.html', property=property_row)


@app.route('/applications', methods=['GET', 'POST'])
@login_required
def applications():
    db = get_db()
    user = current_user()

    if request.method == 'POST' and user['role'] == 'owner':
        app_id = request.form.get('application_id')
        status = request.form.get('status')
        if status in {'pending', 'approved', 'denied'}:
            db.execute('UPDATE applications SET status = ? WHERE id = ?', (status, app_id))
            db.commit()
            flash('Application updated.', 'success')
        return redirect(url_for('applications'))

    if user['role'] == 'owner':
        items = db.execute(
            '''
            SELECT a.*, p.title AS property_title, p.city, u.name AS tenant_name, u.email AS tenant_email
            FROM applications a
            JOIN properties p ON a.property_id = p.id
            JOIN users u ON a.tenant_id = u.id
            WHERE p.owner_id = ?
            ORDER BY a.created_at DESC
            ''',
            (user['id'],),
        ).fetchall()
    else:
        items = db.execute(
            '''
            SELECT a.*, p.title AS property_title, p.city
            FROM applications a
            JOIN properties p ON a.property_id = p.id
            WHERE a.tenant_id = ?
            ORDER BY a.created_at DESC
            ''',
            (user['id'],),
        ).fetchall()
    return render_template('applications.html', applications=items, role=user['role'])


@app.route('/payments', methods=['GET', 'POST'])
@login_required
def payments():
    db = get_db()
    user = current_user()

    if request.method == 'POST' and user['role'] == 'tenant':
        payment_id = request.form.get('payment_id')
        card_name = request.form.get('card_name', '').strip()
        card_number = request.form.get('card_number', '').strip().replace(' ', '')
        if not card_name or len(card_number) < 4:
            flash('Enter card details for the mock payment form.', 'danger')
            return redirect(url_for('payments'))
        db.execute(
            '''
            UPDATE payments
            SET status = 'paid', payment_method = 'Card', card_last4 = ?, paid_at = ?
            WHERE id = ?
            ''',
            (card_number[-4:], now_iso(), payment_id),
        )
        db.commit()
        flash('Mock payment submitted successfully.', 'success')
        return redirect(url_for('payments'))

    if user['role'] == 'owner':
        items = db.execute(
            '''
            SELECT pay.*, p.title AS property_title, u.name AS tenant_name
            FROM payments pay
            JOIN leases l ON pay.lease_id = l.id
            JOIN properties p ON l.property_id = p.id
            JOIN users u ON l.tenant_id = u.id
            WHERE l.owner_id = ?
            ORDER BY pay.due_date ASC
            ''',
            (user['id'],),
        ).fetchall()
    else:
        items = db.execute(
            '''
            SELECT pay.*, p.title AS property_title
            FROM payments pay
            JOIN leases l ON pay.lease_id = l.id
            JOIN properties p ON l.property_id = p.id
            WHERE l.tenant_id = ?
            ORDER BY pay.due_date ASC
            ''',
            (user['id'],),
        ).fetchall()
    return render_template('payments.html', payments=items, role=user['role'])


@app.route('/messages', methods=['GET', 'POST'])
@login_required
def messages():
    db = get_db()
    user = current_user()
    selected_id = request.args.get('conversation_id', type=int)

    if request.method == 'POST':
        conversation_id = request.form.get('conversation_id', type=int)
        body = request.form.get('body', '').strip()
        if conversation_id and body:
            db.execute(
                'INSERT INTO messages (conversation_id, sender_id, body, created_at) VALUES (?, ?, ?, ?)',
                (conversation_id, user['id'], body, now_iso()),
            )
            db.execute('UPDATE conversations SET updated_at = ? WHERE id = ?', (now_iso(), conversation_id))
            db.commit()
            return redirect(url_for('messages', conversation_id=conversation_id))
        flash('Message cannot be empty.', 'danger')
        return redirect(url_for('messages'))

    if user['role'] == 'owner':
        conversations = db.execute(
            '''
            SELECT c.*, p.title AS property_title, u.name AS other_name,
                   (SELECT body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) AS last_message
            FROM conversations c
            JOIN properties p ON c.property_id = p.id
            JOIN users u ON c.tenant_id = u.id
            WHERE c.owner_id = ?
            ORDER BY c.updated_at DESC
            ''',
            (user['id'],),
        ).fetchall()
    else:
        conversations = db.execute(
            '''
            SELECT c.*, p.title AS property_title, u.name AS other_name,
                   (SELECT body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) AS last_message
            FROM conversations c
            JOIN properties p ON c.property_id = p.id
            JOIN users u ON c.owner_id = u.id
            WHERE c.tenant_id = ?
            ORDER BY c.updated_at DESC
            ''',
            (user['id'],),
        ).fetchall()

    selected = None
    messages_ = []
    if conversations:
        if not selected_id:
            selected_id = conversations[0]['id']
        selected = next((c for c in conversations if c['id'] == selected_id), None)
        if selected:
            messages_ = db.execute(
                'SELECT m.*, u.name AS sender_name FROM messages m JOIN users u ON m.sender_id = u.id WHERE conversation_id = ? ORDER BY created_at ASC',
                (selected_id,),
            ).fetchall()
    return render_template('messages.html', conversations=conversations, selected=selected, messages=messages_)


@app.route('/maintenance', methods=['GET', 'POST'])
@login_required
def maintenance():
    db = get_db()
    user = current_user()

    if request.method == 'POST' and user['role'] == 'tenant':
        property_id = request.form.get('property_id', type=int)
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'medium').strip()
        property_row = db.execute('SELECT owner_id FROM properties WHERE id = ?', (property_id,)).fetchone()
        if property_row and title and description:
            db.execute(
                '''
                INSERT INTO maintenance_requests (tenant_id, owner_id, property_id, title, description, priority, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?)
                ''',
                (user['id'], property_row['owner_id'], property_id, title, description, priority, now_iso()),
            )
            db.commit()
            flash('Maintenance request created.', 'success')
            return redirect(url_for('maintenance'))
        flash('Complete all maintenance fields.', 'danger')

    if user['role'] == 'owner':
        items = db.execute(
            '''
            SELECT mr.*, p.title AS property_title, u.name AS tenant_name
            FROM maintenance_requests mr
            JOIN properties p ON mr.property_id = p.id
            JOIN users u ON mr.tenant_id = u.id
            WHERE mr.owner_id = ?
            ORDER BY mr.created_at DESC
            ''',
            (user['id'],),
        ).fetchall()
        properties_owned = []
    else:
        items = db.execute(
            '''
            SELECT mr.*, p.title AS property_title
            FROM maintenance_requests mr
            JOIN properties p ON mr.property_id = p.id
            WHERE mr.tenant_id = ?
            ORDER BY mr.created_at DESC
            ''',
            (user['id'],),
        ).fetchall()
        properties_owned = db.execute(
            'SELECT p.* FROM leases l JOIN properties p ON l.property_id = p.id WHERE l.tenant_id = ? AND l.status = "active"',
            (user['id'],),
        ).fetchall()
    return render_template('maintenance.html', requests=items, role=user['role'], tenant_properties=properties_owned)


with app.app_context():
    init_db()


if __name__ == '__main__':
    app.run(debug=True)
