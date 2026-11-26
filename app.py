"""
Social Media Escalation Portal
Flask backend server - Bright Edition
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import os
import json
import re


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

        # Seed real escalations if empty or <= 3 dummy items
        try:
            current_count = Escalation.query.count()
            json_file = os.path.join(BASE_DIR, "initial_escalations.json")
            if current_count <= 3 and os.path.exists(json_file):
                EscalationUpdate.query.delete()
                Escalation.query.delete()
                db.session.commit()
                with open(json_file, 'r', encoding='utf-8') as f:
                    items = json.load(f)
                to_add = []
                for item in items:
                    esc = Escalation(
                        ticket_no=item['ticket_no'],
                        customer_contact=item.get('customer_contact', ''),
                        customer_name=item.get('customer_name', ''),
                        platform=item.get('platform', 'Email'),
                        escalation_date=item.get('escalation_date', ''),
                        reported_by=item.get('reported_by', ''),
                        assigned_to=item.get('assigned_to', ''),
                        complaint=item.get('complaint', ''),
                        courier_detail=item.get('courier_detail', ''),
                        priority=item.get('priority', 'Medium'),
                        status=item.get('status', 'Open'),
                        resolution=item.get('resolution', ''),
                        eta=item.get('eta', '')
                    )
                    to_add.append(esc)
                db.session.add_all(to_add)
                db.session.commit()
                print(f"[OK] Seeded {len(to_add)} real complaints from initial_escalations.json")
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


# ─────────────────────────── EXCEL IMPORT & EXPORT ───────────────────────────

@app.route('/api/import-excel', methods=['POST'])
def import_excel():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx', '.xlsm', '.xltx')):
        return jsonify({'success': False, 'error': 'Invalid format. Please upload an Excel (.xlsx) file.'}), 400

    try:
        import openpyxl
        wb = openpyxl.load_workbook(file.stream, data_only=True)
        sheet = None
        if 'Coocaa Escalations Oveall' in wb.sheetnames:
            sheet = wb['Coocaa Escalations Oveall']
        elif 'Raw Data' in wb.sheetnames:
            sheet = wb['Raw Data']
        else:
            sheet = wb.active

        headers = [str(c.value).strip() if c.value is not None else '' for c in sheet[1]]

        def find_col(possible_names):
            for name in possible_names:
                for idx, h in enumerate(headers):
                    if name.lower() in h.lower():
                        return idx + 1
            return None

        cno_col = find_col(['complaint number', 'ticket', 'ticket_no', 's.no'])
        name_col = find_col(['customer name', 'name', 'customer'])
        phone_col = find_col(['customer phone', 'phone', 'contact', 'mobile'])
        email_col = find_col(['customer email', 'email'])
        date_col = find_col(['email date', 'date', 'escalation date', 'created'])
        subject_col = find_col(['email subject', 'subject', 'complaint', 'issue details'])
        reason_col = find_col(['escalation reason', 'reason', 'issue'])
        model_col = find_col(['tv model', 'model'])
        state_col = find_col(['state / region', 'state', 'region', 'city'])
        status_col = find_col(['current service status', 'complaint status', 'status'])
        assign_col = find_col(['assigned member', 'assigned to', 'assign to', 'assignee'])
        mailbox_col = find_col(['outlook mailbox', 'reported by', 'mailbox'])
        order_col = find_col(['order id', 'invoice', 'order id / invoice', 'courier'])

        imported_count = 0
        updated_count = 0
        existing_map = {e.ticket_no: e for e in Escalation.query.all()}
        seen_tickets = set(existing_map.keys())

        for r in range(2, sheet.max_row + 1):
            raw_cno = sheet.cell(row=r, column=cno_col).value if cno_col else None
            if raw_cno is None and not any(sheet.cell(row=r, column=c).value for c in range(1, len(headers)+1)):
                continue

            raw_cno_str = str(raw_cno).strip() if raw_cno and str(raw_cno).strip() not in ['None', 'N/A', '-'] else f'IMP-{r:04d}'
            base_t = raw_cno_str
            sfx = 1
            while raw_cno_str in seen_tickets and raw_cno_str not in existing_map:
                raw_cno_str = f"{base_t}-{sfx}"
                sfx += 1
            seen_tickets.add(raw_cno_str)

            cname = str(sheet.cell(row=r, column=name_col).value or '').strip() if name_col else ''
            phone = str(sheet.cell(row=r, column=phone_col).value or '').strip() if phone_col else ''
            if phone.endswith('.0'): phone = phone[:-2]
            email = str(sheet.cell(row=r, column=email_col).value or '').strip() if email_col else ''

            contacts = [p for p in [phone, email] if p and p not in ['None', 'N/A', '-']]
            contact_str = ' | '.join(contacts)

            raw_date = sheet.cell(row=r, column=date_col).value if date_col else None
            date_str = ''
            if raw_date:
                if isinstance(raw_date, datetime):
                    date_str = raw_date.strftime('%Y-%m-%d')
                else:
                    date_str = str(raw_date)[:10].strip()

            raw_st = str(sheet.cell(row=r, column=status_col).value or '').strip() if status_col else 'Open'
            status = 'Open'
            st_lower = raw_st.lower()
            if 'closed' in st_lower or 'cancel' in st_lower or 'replacement processed' in st_lower:
                status = 'Closed'
            elif 'transit' in st_lower or 'awaited' in st_lower or 'pending' in st_lower:
                status = 'Pending'
            elif 'visit' in st_lower or 'progress' in st_lower:
                status = 'In Progress'

            assign_str = str(sheet.cell(row=r, column=assign_col).value or '').strip() if assign_col else 'Unassigned'
            if assign_str in ['None', 'N/A', '-']: assign_str = 'Unassigned'

            courier_val = str(sheet.cell(row=r, column=order_col).value or '').strip() if order_col else ''
            if courier_val in ['None', 'N/A', '-']: courier_val = ''
            if raw_st and raw_st not in ['None', 'N/A', '-']:
                courier_val = f"{courier_val} | Status: {raw_st}" if courier_val else f"Status: {raw_st}"

            subj = str(sheet.cell(row=r, column=subject_col).value or '').strip() if subject_col else ''
            reas = str(sheet.cell(row=r, column=reason_col).value or '').strip() if reason_col else ''
            mod = str(sheet.cell(row=r, column=model_col).value or '').strip() if model_col else ''
            stt = str(sheet.cell(row=r, column=state_col).value or '').strip() if state_col else ''
            parts = [p for p in [subj, f"Reason: {reas}" if reas and reas != subj else "", f"Model: {mod}" if mod else "", f"State: {stt}" if stt else ""] if p and p not in ['None', 'N/A', '-']]
            complaint_text = '\n'.join(parts) if parts else 'Customer escalation.'

            comb = f"{subj} {reas}".lower()
            if 'legal' in comb or 'forum' in comb or 'court' in comb: priority = 'Critical'
            elif 'delay' in comb or 'urgent' in comb: priority = 'High'
            else: priority = 'Medium'

            mb = str(sheet.cell(row=r, column=mailbox_col).value or '').strip() if mailbox_col else 'Email Support'
            if mb in ['None', 'N/A', '-']: mb = 'Email Support'

            if raw_cno_str in existing_map:
                existing = existing_map[raw_cno_str]
                if cname and cname not in ['None', 'N/A', '-']: existing.customer_name = cname
                if contact_str: existing.customer_contact = contact_str
                if date_str: existing.escalation_date = date_str
                if complaint_text: existing.complaint = complaint_text
                if courier_val: existing.courier_detail = courier_val
                if assign_str: existing.assigned_to = assign_str
                existing.status = status
                existing.priority = priority
                existing.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                new_esc = Escalation(
                    ticket_no=raw_cno_str,
                    customer_name=cname if cname and cname not in ['None', 'N/A', '-'] else 'Customer',
                    customer_contact=contact_str,
                    platform='Email',
                    escalation_date=date_str or datetime.utcnow().strftime('%Y-%m-%d'),
                    reported_by=mb,
                    assigned_to=assign_str,
                    complaint=complaint_text,
                    courier_detail=courier_val,
                    priority=priority,
                    status=status
                )
                db.session.add(new_esc)
                existing_map[raw_cno_str] = new_esc
                imported_count += 1

        db.session.commit()
        return jsonify({'success': True, 'imported': imported_count, 'updated': updated_count, 'total': len(existing_map)})
    except Exception as ex:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(ex)}), 500


@app.route('/api/export-excel', methods=['GET'])
def export_excel():
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Escalations"

        headers = [
            "Ticket #", "Platform", "Customer Name", "Customer Contact",
            "Complaint Detail", "Courier Detail", "Reported By", "Assign To",
            "Escalation Date", "Priority", "Status", "Resolution ETA", "Resolution Remarks"
        ]
        ws.append(headers)

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        items = Escalation.query.order_by(Escalation.id.desc()).all()
        for e in items:
            ws.append([
                e.ticket_no,
                e.platform,
                e.customer_name,
                e.customer_contact,
                e.complaint,
                e.courier_detail,
                e.reported_by,
                e.assigned_to,
                e.escalation_date,
                e.priority,
                e.status,
                e.eta,
                e.resolution
            ])

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 50)

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"Escalations_Report_{datetime.utcnow().strftime('%Y%m%d')}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as ex:
        return jsonify({'success': False, 'error': str(ex)}), 500


@app.route('/api/bulk-escalations', methods=['POST'])
def bulk_escalations():
    data = request.json or []
    if not isinstance(data, list):
        return jsonify({'success': False, 'error': 'Expected JSON array'}), 400

    existing = {e.ticket_no: e for e in Escalation.query.all()}
    added = 0
    updated = 0
    for item in data:
        tno = item.get('ticket_no', '').strip()
        if not tno: continue
        if tno in existing:
            e = existing[tno]
            for k in ['customer_name', 'customer_contact', 'platform', 'escalation_date', 'reported_by', 'assigned_to', 'complaint', 'courier_detail', 'priority', 'status', 'resolution', 'eta']:
                if k in item: setattr(e, k, item[k])
            e.updated_at = datetime.utcnow()
            updated += 1
        else:
            new_e = Escalation(
                ticket_no=tno,
                customer_name=item.get('customer_name', ''),
                customer_contact=item.get('customer_contact', ''),
                platform=item.get('platform', 'Email'),
                escalation_date=item.get('escalation_date', ''),
                reported_by=item.get('reported_by', ''),
                assigned_to=item.get('assigned_to', ''),
                complaint=item.get('complaint', ''),
                courier_detail=item.get('courier_detail', ''),
                priority=item.get('priority', 'Medium'),
                status=item.get('status', 'Open'),
                resolution=item.get('resolution', ''),
                eta=item.get('eta', '')
            )
            db.session.add(new_e)
            existing[tno] = new_e
            added += 1
    db.session.commit()
    return jsonify({'success': True, 'added': added, 'updated': updated, 'total': len(existing)})



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
