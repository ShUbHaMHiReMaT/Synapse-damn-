# app.py
import os
import hashlib
import mimetypes
import pdfkit
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, session, send_from_directory,
    jsonify, url_for, abort, Response
)
from db import mysql
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = "super-secret-change-me"

# ---------------- MySQL Config ----------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'hacfy'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

mysql.init_app(app)

# ---------------- PDF CONFIG ----------------
config = None   # For Windows, set wkhtmltopdf.exe path if needed


# ======================================================
#                  HELPER DECORATORS
# ======================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def role_required(roles):
    if not isinstance(roles, (list, tuple)):
        accepted = [roles]
    else:
        accepted = roles

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'role' not in session or session['role'] not in accepted:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


# ======================================================
#                       AUTH
# ======================================================

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.md5(request.form['password'].encode()).hexdigest()

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username, role FROM users WHERE username=%s AND password=%s",
                    (username, password))
        row = cur.fetchone()
        cur.close()

        if row:
            session['user_id'] = row[0]
            session['username'] = row[1]
            session['role'] = row[2]
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ======================================================
#                     DASHBOARD
# ======================================================

@app.route('/dashboard')
@login_required
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) FROM organizations")
    org_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM assessments")
    ass_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM findings")
    find_count = cur.fetchone()[0]
    cur.close()

    return render_template('dashboard.html',
                           org_count=org_count,
                           ass_count=ass_count,
                           find_count=find_count)


# ======================================================
#                ORGANIZATIONS
# ======================================================

@app.route('/orgs')
@login_required
def org_list():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT organizations.id, organizations.name, sectors.sector_name, organizations.created_at
        FROM organizations 
        LEFT JOIN sectors ON organizations.sector_id = sectors.id
        ORDER BY organizations.created_at DESC
    """)
    orgs = cur.fetchall()
    cur.close()

    return render_template('org_list.html', orgs=orgs)


@app.route('/orgs/create', methods=['GET', 'POST'])
@login_required
def org_create():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, sector_name FROM sectors ORDER BY sector_name")
    sectors = cur.fetchall()

    if request.method == 'POST':
        name = request.form['name']
        sector_id = request.form['sector']

        cur.execute(
            "INSERT INTO organizations(name, sector_id) VALUES (%s,%s)",
            (name, sector_id))
        mysql.connection.commit()

        org_id = cur.lastrowid
        cur.close()

        return redirect(url_for('assessment_create', org_id=org_id))

    cur.close()
    return render_template('org_create.html', sectors=sectors)


# ======================================================
#                     ASSESSMENTS
# ======================================================

@app.route('/assessments')
@login_required
def assessment_list():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT a.id, o.name, a.start_date, a.end_date, a.status
        FROM assessments a
        JOIN organizations o ON a.organization_id = o.id
        ORDER BY a.created_at DESC
    """)
    assessments = cur.fetchall()
    cur.close()

    return render_template('assessment_list.html', assessments=assessments)


@app.route('/assessments/create/<int:org_id>', methods=['GET', 'POST'])
@login_required
def assessment_create(org_id):
    if request.method == 'POST':
        scope = request.form['scope']
        sd = request.form['sd'] or None
        ed = request.form['ed'] or None

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO assessments(organization_id, scope_description, start_date, end_date)
            VALUES(%s,%s,%s,%s)
        """, (org_id, scope, sd, ed))

        mysql.connection.commit()
        ass_id = cur.lastrowid
        cur.close()

        return redirect(url_for('finding_create', ass_id=ass_id))

    return render_template('assessment_create.html', org_id=org_id)


@app.route('/assessments/<int:ass_id>/view')
@login_required
def assessment_view(ass_id):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT a.id, a.scope_description, a.start_date, a.end_date, a.status,
               o.name AS org_name, s.sector_name
        FROM assessments a
        JOIN organizations o ON a.organization_id = o.id
        LEFT JOIN sectors s ON o.sector_id = s.id
        WHERE a.id=%s
    """, (ass_id,))
    assessment = cur.fetchone()

    cur.execute("""
        SELECT id, title, severity, cvss_vector, cvss_score, owasp_category,
               description, sector_impact, recommendation, created_at
        FROM findings 
        WHERE assessment_id=%s 
        ORDER BY created_at DESC
    """, (ass_id,))
    findings = cur.fetchall()

    cur.close()

    return render_template('report_view.html',
                           assessment=assessment,
                           findings=findings)


# ======================================================
#              EXPORT FORMATS (PDF, HTML, CSV, JSON)
# ======================================================

def assessment_view_render_html(ass_id):
    """Render report_view.html as plain HTML string."""
    with app.test_request_context():
        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT a.id, a.scope_description, a.start_date, a.end_date, a.status,
                   o.name AS org_name, s.sector_name
            FROM assessments a
            JOIN organizations o ON a.organization_id = o.id
            LEFT JOIN sectors s ON o.sector_id = s.id
            WHERE a.id=%s
        """, (ass_id,))
        assessment = cur.fetchone()

        cur.execute("""
            SELECT id, title, severity, cvss_vector, cvss_score, owasp_category,
                   description, sector_impact, recommendation, created_at
            FROM findings 
            WHERE assessment_id=%s 
            ORDER BY created_at
        """, (ass_id,))
        findings = cur.fetchall()

        cur.close()

        return render_template('report_view.html',
                               assessment=assessment,
                               findings=findings)


# ---------- PDF ----------
@app.route('/assessments/<int:ass_id>/export/pdf')
@login_required
def export_pdf(ass_id):
    html = assessment_view_render_html(ass_id)

    options = {'enable-local-file-access': None}

    try:
        pdf = pdfkit.from_string(html, False, options=options, configuration=config)
        return (pdf, 200, {
            'Content-Type': 'application/pdf',
            'Content-Disposition': f'attachment; filename=assessment_{ass_id}.pdf'
        })
    except Exception as e:
        return f"PDF export failed: {e}", 500


# ---------- HTML ----------
@app.route('/assessments/<int:ass_id>/export/html')
@login_required
def export_html(ass_id):
    html = assessment_view_render_html(ass_id)
    return (html, 200, {
        "Content-Type": "text/html",
        "Content-Disposition": f"attachment; filename=assessment_{ass_id}.html"
    })


# ---------- JSON ----------
@app.route('/assessments/<int:ass_id>/export/json')
@login_required
def export_json(ass_id):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT a.id, a.scope_description, a.start_date, a.end_date, a.status,
               o.name AS org_name, s.sector_name
        FROM assessments a
        JOIN organizations o ON a.organization_id=o.id
        LEFT JOIN sectors s ON o.sector_id=s.id
        WHERE a.id=%s
    """, (ass_id,))
    assessment = cur.fetchone()

    cur.execute("""
        SELECT id, title, severity, cvss_vector, cvss_score, owasp_category,
               description, sector_impact, recommendation
        FROM findings WHERE assessment_id=%s
    """, (ass_id,))
    findings = cur.fetchall()

    cur.close()

    keys_ass = ("id", "scope", "start_date", "end_date",
                "status", "organization", "sector")
    keys_f = ("id", "title", "severity", "cvss_vector", "cvss_score",
              "owasp", "description", "impact", "recommendation")

    json_data = {
        "assessment": dict(zip(keys_ass, assessment)),
        "findings": [dict(zip(keys_f, row)) for row in findings]
    }

    return jsonify(json_data)


# ---------- CSV ----------
@app.route('/assessments/<int:ass_id>/export/csv')
@login_required
def export_csv(ass_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, title, severity, cvss_vector, cvss_score,
               owasp_category, description, sector_impact, recommendation
        FROM findings WHERE assessment_id=%s
    """, (ass_id,))
    rows = cur.fetchall()
    cur.close()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID", "Title", "Severity", "CVSS Vector", "CVSS Score",
        "OWASP Category", "Description", "Sector Impact", "Recommendation"
    ])

    for row in rows:
        writer.writerow(row)

    return Response(output.getvalue(),
                    mimetype="text/csv",
                    headers={
                        "Content-Disposition": f"attachment; filename=assessment_{ass_id}.csv"
                    })


# ======================================================
#                     FINDINGS
# ======================================================

@app.route('/findings')
@login_required
def finding_list_all():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT f.id, f.title, f.severity, f.cvss_score, f.owasp_category,
               o.name AS org_name, a.id AS assessment_id
        FROM findings f
        JOIN assessments a ON f.assessment_id = a.id
        JOIN organizations o ON a.organization_id = o.id
        ORDER BY f.created_at DESC
    """)
    findings = cur.fetchall()
    cur.close()

    return render_template('finding_list.html', findings=findings)


@app.route('/findings/create/<int:ass_id>', methods=['GET', 'POST'])
@login_required
def finding_create(ass_id):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT o.sector_id 
        FROM assessments a 
        JOIN organizations o ON a.organization_id=o.id 
        WHERE a.id=%s
    """, (ass_id,))
    row = cur.fetchone()

    sector_template = None
    if row:
        sector_id = row[0]
        cur.execute("""
            SELECT impact_template, recommendation_template
            FROM sector_templates
            WHERE sector_id=%s LIMIT 1
        """, (sector_id,))
        sector_template = cur.fetchone()

    if request.method == 'POST':
        title = request.form['title']
        severity = request.form['severity']
        description = request.form['description']
        cvss_vector = request.form.get('cvss_vector', '')
        cvss_score = request.form.get('cvss_score') or None
        owasp = request.form.get('owasp_category', '')

        cur.execute("""
            INSERT INTO findings 
            (assessment_id, title, severity, cvss_vector, cvss_score,
             owasp_category, description, sector_impact, recommendation)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            ass_id, title, severity, cvss_vector, cvss_score, owasp,
            description,
            sector_template[0] if sector_template else None,
            sector_template[1] if sector_template else None
        ))

        mysql.connection.commit()
        find_id = cur.lastrowid
        cur.close()

        return redirect(url_for('evidence_upload', find_id=find_id))

    cur.close()
    return render_template('finding_create.html',
                           ass_id=ass_id,
                           template=sector_template)


# ======================================================
#                  EVIDENCE
# ======================================================

@app.route('/evidence/upload/<int:find_id>', methods=['GET', 'POST'])
@login_required
def evidence_upload(find_id):
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file part", 400

        file = request.files['file']
        if file.filename == '':
            return "No selected file", 400

        save_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(find_id))
        os.makedirs(save_dir, exist_ok=True)

        safe_name = file.filename.replace("/", "_").replace("\\", "_")
        path = os.path.join(save_dir, safe_name)
        file.save(path)

        # -------- FIXED LINE BELOW --------
        file_size = os.path.getsize(path)

        mime_type, _ = mimetypes.guess_type(path)
        mime_type = mime_type or "application/octet-stream"
        ocr_text = "OCR not enabled in this version."

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO evidence 
            (finding_id, file_path, file_size, mime_type, ocr_text)
            VALUES (%s,%s,%s,%s,%s)
        """, (find_id, path, file_size, mime_type, ocr_text))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('finding_view', find_id=find_id))

    return render_template('evidence_upload.html', find_id=find_id)


@app.route('/evidence/preview/<int:find_id>/<path:filename>')
@login_required
def evidence_preview(find_id, filename):
    dir_path = os.path.join(app.config['UPLOAD_FOLDER'], str(find_id))
    return send_from_directory(dir_path, filename)


@app.route('/findings/<int:find_id>')
@login_required
def finding_view(find_id):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT f.*, a.id as assessment_id, o.name as org_name
        FROM findings f
        JOIN assessments a ON f.assessment_id = a.id
        JOIN organizations o ON a.organization_id = o.id
        WHERE f.id=%s
    """, (find_id,))
    finding = cur.fetchone()

    cur.execute("""
        SELECT id, file_path, file_size, mime_type, uploaded_at 
        FROM evidence 
        WHERE finding_id=%s ORDER BY uploaded_at DESC
    """, (find_id,))
    evidence = cur.fetchall()
    cur.close()

    preview_items = []
    for e in evidence:
        fp = e[1]
        fname = os.path.basename(fp)
        preview_url = url_for('evidence_preview', find_id=find_id, filename=fname)

        preview_items.append({
            "id": e[0],
            "file": fname,
            "size": e[2],
            "mime": e[3],
            "uploaded_at": e[4],
            "preview_url": preview_url
        })

    return render_template('finding_view.html',
                           finding=finding,
                           evidence=preview_items)


# ======================================================
#          ASSESSMENT STATUS + DEMO DATA
# ======================================================

@app.route('/assessments/<int:ass_id>/status', methods=['POST'])
@login_required
@role_required(['Admin', 'Manager'])
def assessment_status_update(ass_id):
    new_status = request.form.get('status')

    if new_status not in ["Open", "In Progress", "Fixed", "Re-tested", "Closed"]:
        return "Invalid status", 400

    cur = mysql.connection.cursor()
    cur.execute("UPDATE assessments SET status=%s WHERE id=%s",
                (new_status, ass_id))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('assessment_view', ass_id=ass_id))


# ======================================================
#                    API ENDPOINTS
# ======================================================

@app.route('/api/v1/orgs')
def api_orgs():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, name, sector_id, created_at
        FROM organizations ORDER BY id DESC
    """)
    rows = cur.fetchall()
    cur.close()

    keys = ('id', 'name', 'sector_id', 'created_at')
    return jsonify([dict(zip(keys, row)) for row in rows])


@app.route('/api/v1/assessments/<int:org_id>')
def api_assessments(org_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, organization_id, scope_description, start_date, end_date, status
        FROM assessments WHERE organization_id=%s
    """, (org_id,))
    rows = cur.fetchall()
    cur.close()

    keys = ('id', 'organization_id', 'scope_description',
            'start_date', 'end_date', 'status')

    return jsonify([dict(zip(keys, row)) for row in rows])


@app.route('/api/v1/findings/<int:ass_id>')
def api_findings(ass_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, assessment_id, title, severity, cvss_vector, cvss_score, owasp_category
        FROM findings WHERE assessment_id=%s
    """, (ass_id,))
    rows = cur.fetchall()
    cur.close()

    keys = ('id', 'assessment_id', 'title', 'severity',
            'cvss_vector', 'cvss_score', 'owasp_category')

    return jsonify([dict(zip(keys, row)) for row in rows])


# ======================================================
#                     RUN SERVER
# ======================================================

if __name__ == '__main__':
    app.run(debug=True)
