"""
Social Media Escalation Portal
Flask backend server - Bright Edition
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = 'escalation_portal_secret_2024'
CORS(app)

# Database config
db_url = os.environ.get('DATABASE_URL')
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "escalations.db")}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ─────────────────────────── MODELS ───────────────────────────

class Escalation(db.Model):
    __tablename__ = 'escalations'
    id               = db.Column(db.Integer, primary_key=True)
    ticket_no        = db.Column(db.String(50), unique=True, nullable=False)
    customer_contact = db.Column(db.String(100))
    customer_name    = db.Column(db.String(150))
    platform         = db.Column(db.String(50), nullable=False)   # Facebook, Linkedin, Email, Whatsapp, Call, Instagram
    escalation_date  = db.Column(db.String(30))                  # Date of customer escalation
    reported_by      = db.Column(db.String(100))                  # Vipin, Chandani
    assigned_to      = db.Column(db.String(100))                  # Ajay, Anupam, Monika
    complaint        = db.Column(db.Text, nullable=False)
    courier_detail   = db.Column(db.Text)                         # Courier tracking/dispatch info
    priority         = db.Column(db.String(20), default='Medium')  # Low, Medium, High, Critical
    status           = db.Column(db.String(30), default='Open')    # Open, In Progress, Pending, Resolved, Closed
    resolution       = db.Column(db.Text)
    eta              = db.Column(db.String(20))                    # ETA date e.g. 2026-10-20
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updates          = db.relationship('EscalationUpdate', backref='escalation', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_no': self.ticket_no,
            'customer_contact': self.customer_contact or '',
            'customer_name': self.customer_name or '',
            'platform': self.platform or 'Whatsapp',
            'escalation_date': self.escalation_date or (self.created_at.strftime('%Y-%m-%d') if self.created_at else ''),
            'reported_by': self.reported_by or '',
            'assigned_to': self.assigned_to or '',
            'complaint': self.complaint or '',
            'courier_detail': self.courier_detail or '',
            'priority': self.priority or 'Medium',
            'status': self.status or 'Open',
            'resolution': self.resolution or '',
            'eta': self.eta or '',
            'created_at': self.created_at.strftime('%d-%m-%Y %H:%M') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%d-%m-%Y %H:%M') if self.updated_at else '',
            'updates': [u.to_dict() for u in self.updates]
        }


class EscalationUpdate(db.Model):
    __tablename__ = 'escalation_updates'
    id            = db.Column(db.Integer, primary_key=True)
    escalation_id = db.Column(db.Integer, db.ForeignKey('escalations.id'), nullable=False)
    updated_by    = db.Column(db.String(100), nullable=False)
    note          = db.Column(db.Text, nullable=False)
    status_change = db.Column(db.String(30))
    timestamp     = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'updated_by': self.updated_by,
            'note': self.note,
            'status_change': self.status_change,
            'timestamp': self.timestamp.strftime('%d-%m-%Y %H:%M') if self.timestamp else ''
        }


# ─────────────────────────── INITIALIZE DATABASE ───────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        # Auto-migration for SQLite or PostgreSQL if columns are missing
        try:
            engine = db.engine
            with engine.connect() as conn:
                if 'sqlite' in str(engine.url):
                    cols = [row[1] for row in conn.execute(db.text("PRAGMA table_info(escalations)")).fetchall()]
                    if cols:
                        if 'courier_detail' not in cols:
                            conn.execute(db.text("ALTER TABLE escalations ADD COLUMN courier_detail TEXT"))
                        if 'escalation_date' not in cols:
                            conn.execute(db.text("ALTER TABLE escalations ADD COLUMN escalation_date VARCHAR(30)"))
                        conn.commit()
                elif 'postgresql' in str(engine.url):
                    conn.execute(db.text("ALTER TABLE escalations ADD COLUMN IF NOT EXISTS courier_detail TEXT"))
                    conn.execute(db.text("ALTER TABLE escalations ADD COLUMN IF NOT EXISTS escalation_date VARCHAR(30)"))
                    conn.commit()
        except Exception as e:
            print(f"Migration notice: {e}")

        # Seed sample escalations if empty so dashboard is active immediately
        try:
            if Escalation.query.count() == 0:
                sample_items = [
                    Escalation(
                        ticket_no="ESC-2024-001",
                        customer_contact="+91 98765 43210",
                        customer_name="Rahul Sharma",
                        platform="Whatsapp",
                        escalation_date=datetime.utcnow().strftime('%Y-%m-%d'),
                        reported_by="Vipin",
                        assigned_to="Ajay",
                        complaint="Smart TV display panel flickering intermittently. Customer requesting urgent technician visit.",
                        courier_detail="Bluedart AWB #BLU-882910 - Replacement board in transit",
                        priority="High",
                        status="In Progress",
                        eta=datetime.utcnow().strftime('%Y-%m-%d')
                    ),
                    Escalation(
                        ticket_no="ESC-2024-002",
                        customer_contact="+91 91234 56789",
                        customer_name="Pooja Verma",
                        platform="Instagram",
                        escalation_date=datetime.utcnow().strftime('%Y-%m-%d'),
                        reported_by="Chandani",
                        assigned_to="Anupam",
                        complaint="Sound bar power cable missing in delivery parcel. Customer escalation on social handle.",
                        courier_detail="Delhivery Tracking #DL-993821 - Dispatched adapter",
                        priority="Medium",
                        status="Open",
                        eta=datetime.utcnow().strftime('%Y-%m-%d')
                    ),
                    Escalation(
                        ticket_no="ESC-2024-003",
                        customer_contact="+91 99887 76655",
                        customer_name="Vikram Mehta",
                        platform="Facebook",
                        escalation_date=datetime.utcnow().strftime('%Y-%m-%d'),
                        reported_by="Vipin",
                        assigned_to="Monika",
                        complaint="Delayed installation service post-delivery. Customer requested morning time slot.",
                        courier_detail="Product delivered on 12-Oct by DTDC",
                        priority="Critical",
                        status="Pending",
                        eta=datetime.utcnow().strftime('%Y-%m-%d')
                    )
                ]
                db.session.add_all(sample_items)
                db.session.commit()
        except Exception as e:
            print(f"Seed notice: {e}")

init_db()


# ─────────────────────────── ROUTES ───────────────────────────

@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/new')
def new_escalation_page():
    return render_template('new_escalation.html')


@app.route('/detail/<int:esc_id>')
def detail_page(esc_id):
    return render_template('detail.html', esc_id=esc_id)


@app.route('/team')
def team_page():
    # Team section removed per request; redirect to dashboard
    return redirect(url_for('dashboard'))


# ─────────────────────────── API ───────────────────────────

@app.route('/api/escalations', methods=['GET'])
def get_escalations():
    status   = request.args.get('status')
    platform = request.args.get('platform')
    priority = request.args.get('priority')
    search   = request.args.get('search', '').strip()

    q = Escalation.query
    if status:   q = q.filter_by(status=status)
    if platform: q = q.filter_by(platform=platform)
    if priority: q = q.filter_by(priority=priority)
    if search:
        term = f"%{search}%"
        q = q.filter(
            db.or_(
                Escalation.ticket_no.like(term),
                Escalation.customer_name.like(term),
                Escalation.customer_contact.like(term),
                Escalation.complaint.like(term),
                Escalation.courier_detail.like(term),
                Escalation.assigned_to.like(term),
                Escalation.reported_by.like(term),
                Escalation.platform.like(term)
            )
        )
    esc_list = q.order_by(Escalation.updated_at.desc()).all()
    return jsonify([e.to_dict() for e in esc_list])


@app.route('/api/escalations', methods=['POST'])
def create_escalation():
    data = request.json or {}
    ticket = data.get('ticket_no', '').strip()
    if not ticket:
        return jsonify({'success': False, 'error': 'Ticket number is required'}), 400
    
    # Check uniqueness
    if Escalation.query.filter_by(ticket_no=ticket).first():
        return jsonify({'success': False, 'error': f'Ticket number "{ticket}" already exists'}), 409
    
    esc_date = data.get('escalation_date', '').strip()
    if not esc_date:
        esc_date = datetime.utcnow().strftime('%Y-%m-%d')

    esc = Escalation(
        ticket_no        = ticket,
        customer_contact = data.get('customer_contact', '').strip(),
        customer_name    = data.get('customer_name', '').strip(),
        platform         = data.get('platform', 'Whatsapp').strip(),
        escalation_date  = esc_date,
        reported_by      = data.get('reported_by', '').strip(),
        assigned_to      = data.get('assigned_to', '').strip(),
        complaint        = data.get('complaint', '').strip(),
        courier_detail   = data.get('courier_detail', '').strip(),
        priority         = data.get('priority', 'Medium') or 'Medium',
        status           = data.get('status', 'Open') or 'Open',
        eta              = data.get('eta', '').strip(),
    )
    db.session.add(esc)
    db.session.flush()

    # auto first update in timeline
    update = EscalationUpdate(
        escalation_id = esc.id,
        updated_by    = data.get('reported_by', 'System') or 'System',
        note          = 'Complaint registered.',
        status_change = esc.status,
    )
    db.session.add(update)
    db.session.commit()
    return jsonify({'success': True, 'ticket_no': ticket, 'id': esc.id}), 201


@app.route('/api/escalations/<int:esc_id>', methods=['GET'])
def get_escalation(esc_id):
    esc = Escalation.query.get_or_404(esc_id)
    return jsonify(esc.to_dict())


@app.route('/api/escalations/<int:esc_id>', methods=['PUT'])
def update_escalation(esc_id):
    esc = Escalation.query.get_or_404(esc_id)
    data = request.json or {}
    old_status = esc.status

    if 'platform' in data:         esc.platform = data['platform']
    if 'customer_name' in data:    esc.customer_name = data['customer_name']
    if 'customer_contact' in data: esc.customer_contact = data['customer_contact']
    if 'complaint' in data:        esc.complaint = data['complaint']
    if 'courier_detail' in data:   esc.courier_detail = data['courier_detail']
    if 'escalation_date' in data:  esc.escalation_date = data['escalation_date']
    if 'reported_by' in data:      esc.reported_by = data['reported_by']
    if 'assigned_to' in data:      esc.assigned_to = data['assigned_to']
    if 'priority' in data:         esc.priority = data['priority']
    if 'status' in data:           esc.status = data['status']
    if 'resolution' in data:       esc.resolution = data['resolution']
    if 'eta' in data:              esc.eta = data['eta']
    
    esc.updated_at = datetime.utcnow()

    note = data.get('update_note', 'Details updated.').strip() or 'Details updated.'
    updated_by = data.get('updated_by', 'Team') or 'Team'
    status_change = esc.status if esc.status != old_status else None

    update = EscalationUpdate(
        escalation_id = esc.id,
        updated_by    = updated_by,
        note          = note,
        status_change = status_change,
    )
    db.session.add(update)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/escalations/<int:esc_id>/update', methods=['POST'])
def add_update(esc_id):
    esc = Escalation.query.get_or_404(esc_id)
    data = request.json or {}
    old_status = esc.status

    new_status   = data.get('status')
    new_priority = data.get('priority')
    new_eta      = data.get('eta')
    new_courier  = data.get('courier_detail')
    new_assigned = data.get('assigned_to')

    if new_status:             esc.status = new_status
    if new_priority:           esc.priority = new_priority
    if new_eta is not None:    esc.eta = new_eta
    if new_courier is not None: esc.courier_detail = new_courier
    if new_assigned:           esc.assigned_to = new_assigned
    
    esc.updated_at = datetime.utcnow()

    update = EscalationUpdate(
        escalation_id = esc.id,
        updated_by    = data.get('updated_by', 'Team') or 'Team',
        note          = data.get('note', '') or 'Status / details updated.',
        status_change = new_status if new_status and new_status != old_status else None,
    )
    db.session.add(update)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/escalations/<int:esc_id>', methods=['DELETE'])
def delete_escalation(esc_id):
    esc = Escalation.query.get_or_404(esc_id)
    db.session.delete(esc)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    total    = Escalation.query.count()
    open_c   = Escalation.query.filter_by(status='Open').count()
    inprog   = Escalation.query.filter_by(status='In Progress').count()
    pending  = Escalation.query.filter_by(status='Pending').count()
    resolved = Escalation.query.filter_by(status='Resolved').count()
    closed   = Escalation.query.filter_by(status='Closed').count()
    critical = Escalation.query.filter_by(priority='Critical').count()
    high     = Escalation.query.filter_by(priority='High').count()

    by_platform = db.session.query(
        Escalation.platform, db.func.count(Escalation.id)
    ).group_by(Escalation.platform).all()

    return jsonify({
        'total': total,
        'open': open_c,
        'in_progress': inprog,
        'pending': pending,
        'resolved': resolved,
        'closed': closed,
        'critical': critical,
        'high': high,
        'by_platform': [{'platform': p, 'count': c} for p, c in by_platform]
    })


# ─────────────────────────── MAIN ───────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"\n[OK] Escalation Portal running in Bright Theme!")
    print(f"   Local:    http://127.0.0.1:5050")
    print(f"   Network:  http://{local_ip}:5050  (share with team)\n")
    app.run(host='0.0.0.0', port=5050, debug=False, use_reloader=False)
