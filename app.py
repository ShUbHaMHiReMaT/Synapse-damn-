from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")  # change in prod

# Context processor to expose current year
@app.context_processor
def inject_now():
    return {'current_year': datetime.now().year}

@app.route('/', methods=['GET', 'POST'])
def upload():
    # Demo POST behavior: accept files but do nothing (flash a message)
    if request.method == 'POST':
        files = request.files.getlist('all_files[]')
        if not files or files == [None] or len(files) == 0:
            flash("No files selected.", "warning")
            return redirect(url_for('upload'))
        # For demo only: don't save files. In real app, forward to Apps Script or save to server.
        flash(f"Received {len(files)} file(s) (demo). Backend integration pending.", "success")
        return redirect(url_for('upload'))

    return render_template('upload.html', upload_action=url_for('upload'))

@app.route('/admin')
def admin():
    # In a real app you'd read claims from a DB or Google Sheet.
    # For the demo we just render the static admin page.
    return render_template('admin.html')

# Optional simple health route
@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

if __name__ == '__main__':
    # Enable debug only during development
    app.run(debug=True, port=5000)
