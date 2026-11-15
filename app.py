import os, datetime as dt
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me')
uri = os.environ.get('DATABASE_URL', 'sqlite:///ccms.db')
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
db = SQLAlchemy(app)

# Auto-routing table: category -> department
ROUTES = {'Hostel': 'Hostel Office', 'Academic': 'Academic Office', 'IT / Network': 'IT Cell',
          'Mess': 'Mess Committee', 'Infrastructure': 'Maintenance', 'Library': 'Library',
          'Transport': 'Transport Office', 'Other': 'Administration Office'}
LEVELS = ['Department Staff', 'Department Head', 'Administration']
SLA_HOURS = int(os.environ.get('SLA_HOURS', 48))
STATUSES = ['Pending', 'In-Progress', 'Resolved', 'Rejected', 'Closed']

def now(): return dt.datetime.utcnow()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    pw = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student, staff, dept, admin
    department = db.Column(db.String(50))

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User')
    category = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    photo = db.Column(db.LargeBinary)
    photo_mime = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Pending')
    department = db.Column(db.String(50))
    level = db.Column(db.Integer, default=0)
    remarks = db.Column(db.Text)
    rating = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    created = db.Column(db.DateTime, default=now)
    sla_due = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)

def seed():
    if not User.query.filter_by(email='admin@campus.edu').first():
        db.session.add(User(name='Administrator', email='admin@campus.edu', pw=generate_password_hash('admin123'), role='admin'))
    for i, d in enumerate(ROUTES.values()):
        e = 'dept%d@campus.edu' % (i + 1)
        if not User.query.filter_by(email=e).first():
            db.session.add(User(name=d + ' Staff', email=e, pw=generate_password_hash('dept123'), role='dept', department=d))
    db.session.commit()

with app.app_context():
    db.create_all(); seed()

def me(): return db.session.get(User, session['uid']) if 'uid' in session else None

def login_required(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            u = me()
            if not u: return redirect(url_for('login'))
            if roles and u.role not in roles: abort(403)
            return f(*a, **k)
        return w
    return deco

@app.before_request
def escalate():  # SLA timer: overdue open complaints move up one level
    open_c = Complaint.query.filter(Complaint.status.in_(['Pending', 'In-Progress']),
                                    Complaint.sla_due < now(), Complaint.level < 2).all()
    for c in open_c:
        c.level += 1; c.sla_due = now() + dt.timedelta(hours=SLA_HOURS)
    if open_c: db.session.commit()

@app.context_processor
def inject(): return dict(user=me(), LEVELS=LEVELS)

@app.route('/')
def index(): return redirect(url_for('dashboard') if me() else url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        f = request.form
        if User.query.filter_by(email=f['email'].lower()).first():
            flash('Email already registered.'); return render_template('register.html')
        role = f['role'] if f['role'] in ('student', 'staff') else 'student'
        db.session.add(User(name=f['name'], email=f['email'].lower(), pw=generate_password_hash(f['password']), role=role))
        db.session.commit(); flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form['email'].lower()).first()
        if u and check_password_hash(u.pw, request.form['password']):
            session['uid'] = u.id; return redirect(url_for('dashboard'))
        flash('Invalid email or password.')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required()
def dashboard():
    u = me(); q = Complaint.query
    if u.role in ('student', 'staff'): q = q.filter_by(user_id=u.id)
    elif u.role == 'dept': q = q.filter_by(department=u.department)
    s = request.args.get('status')
    if s: q = q.filter_by(status=s)
    return render_template('list.html', items=q.order_by(Complaint.id.desc()).all(), s=s, STATUSES=STATUSES)

@app.route('/new', methods=['GET', 'POST'])
@login_required('student', 'staff')
def new():
    if request.method == 'POST':
        f = request.form
        if f['category'] not in ROUTES: abort(400)
        c = Complaint(user_id=me().id, category=f['category'], title=f['title'], description=f['description'],
                      department=ROUTES[f['category']], sla_due=now() + dt.timedelta(hours=SLA_HOURS))
        p = request.files.get('photo')
        if p and p.filename and p.mimetype.startswith('image/'):
            c.photo, c.photo_mime = p.read(), p.mimetype
        db.session.add(c); db.session.commit()
        flash('Complaint #%d registered and routed to %s.' % (c.id, c.department))
        return redirect(url_for('view', cid=c.id))
    return render_template('new.html', cats=ROUTES)

def get_allowed(cid):
    c = db.get_or_404(Complaint, cid); u = me()
    if u.role == 'admin' or c.user_id == u.id or (u.role == 'dept' and u.department == c.department): return c
    abort(403)

@app.route('/c/<int:cid>')
@login_required()
def view(cid): return render_template('view.html', c=get_allowed(cid))

@app.route('/photo/<int:cid>')
@login_required()
def photo(cid):
    c = get_allowed(cid)
    if not c.photo: abort(404)
    return Response(c.photo, mimetype=c.photo_mime)

@app.route('/c/<int:cid>/update', methods=['POST'])
@login_required('dept', 'admin')
def update(cid):
    c = get_allowed(cid); st = request.form['status']
    if st not in ('Pending', 'In-Progress', 'Resolved', 'Rejected'): abort(400)
    c.status, c.remarks = st, request.form.get('remarks', '')
    if st == 'Resolved': c.resolved_at = now()
    db.session.commit(); flash('Status updated.')
    return redirect(url_for('view', cid=cid))

@app.route('/c/<int:cid>/feedback', methods=['POST'])
@login_required('student', 'staff')
def feedback(cid):
    c = get_allowed(cid)
    if c.user_id != me().id or c.status != 'Resolved': abort(403)
    c.rating, c.feedback = int(request.form['rating']), request.form.get('feedback', '')
    if request.form['satisfied'] == 'yes': c.status = 'Closed'
    else: c.status, c.resolved_at, c.sla_due = 'Pending', None, now() + dt.timedelta(hours=SLA_HOURS)
    db.session.commit(); flash('Thank you. ' + ('Ticket closed.' if c.status == 'Closed' else 'Complaint re-opened.'))
    return redirect(url_for('view', cid=cid))

@app.route('/admin')
@login_required('admin')
def admin():
    cs = Complaint.query.all(); by_status = {s: 0 for s in STATUSES}; by_cat = {k: 0 for k in ROUTES}
    dept = {d: dict(total=0, open=0, hrs=[], esc=0) for d in ROUTES.values()}
    for c in cs:
        by_status[c.status] += 1; by_cat[c.category] += 1
        d = dept[c.department]; d['total'] += 1; d['esc'] += c.level > 0
        if c.status in ('Pending', 'In-Progress'): d['open'] += 1
        if c.resolved_at: d['hrs'].append((c.resolved_at - c.created).total_seconds() / 3600)
    for d in dept.values(): d['avg'] = round(sum(d['hrs']) / len(d['hrs']), 1) if d['hrs'] else '-'
    hot = sorted(((c.category, c.title.lower().strip()) for c in cs), key=lambda x: x)
    rec = {}
    for k in hot: rec[k] = rec.get(k, 0) + 1
    rec = [(k[0], k[1], n) for k, n in rec.items() if n > 1]
    return render_template('admin.html', total=len(cs), by_status=by_status, by_cat=by_cat, dept=dept, rec=rec)

if __name__ == '__main__':
    app.run(debug=True)
