"""
app.py — WIFINCE Flask Backend
New flow:
  - /login        → Teacher (ID+password) or Student (roll number)
  - /teacher      → Teacher dashboard (session required)
  - /student      → Student auto-detect page (roll number once, then MAC saved)
  - ARP scan auto-marks students present when they're on teacher's hotspot
"""
import os
import csv
import io
import socket
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, jsonify,
                   make_response, session, redirect, url_for)

from database import get_db, init_db
from scanner  import scan_network, get_mac_for_ip
from seed     import seed_all

app = Flask(__name__)
app.secret_key = "wifince-secret-2024-xk9"   # change in production


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def get_client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else request.remote_addr


def teacher_required(f):
    """Decorator — redirect to login if teacher not logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("teacher_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if session.get("teacher_id"):
        return redirect(url_for("teacher_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    data     = request.get_json(force=True)
    role     = data.get("role")           # "teacher" | "student"

    if role == "teacher":
        tid  = data.get("teacher_id", "").strip()
        pwd  = data.get("password",   "").strip()
        conn = get_db()
        row  = conn.execute(
            "SELECT * FROM teachers WHERE teacher_id=? AND password=?", (tid, pwd)
        ).fetchone()
        conn.close()
        if not row:
            return jsonify({"success": False, "error": "Invalid ID or password"}), 401
        session["teacher_id"]   = row["id"]
        session["teacher_name"] = row["name"]
        return jsonify({"success": True, "redirect": "/teacher"})

    elif role == "student":
        roll = data.get("roll", "").strip().upper()
        conn = get_db()
        student = conn.execute(
            "SELECT * FROM students WHERE roll=?", (roll,)
        ).fetchone()
        conn.close()
        if not student:
            return jsonify({"success": False, "error": "Roll number not found"}), 404
        # Store in session so student page knows who they are
        session["student_id"]   = student["id"]
        session["student_roll"] = student["roll"]
        session["student_name"] = student["name"]
        return jsonify({"success": True, "redirect": "/student"})

    return jsonify({"success": False, "error": "Invalid role"}), 400


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/teacher")
@teacher_required
def teacher_dashboard():
    return render_template("teacher.html",
                           teacher_name=session.get("teacher_name", "Teacher"),
                           lan_ip=get_lan_ip())


@app.route("/student")
def student_page():
    # If student not logged in, redirect to login
    if not session.get("student_id"):
        return redirect(url_for("login") + "?role=student")

    student_id   = session["student_id"]
    student_name = session["student_name"]
    student_roll = session["student_roll"]

    # ── Auto-detect this student's MAC from their IP ──────────────
    client_ip = get_client_ip()
    mac       = get_mac_for_ip(client_ip)

    conn = get_db()

    # Save MAC permanently if not saved yet
    student = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if mac and not student["mac_address"]:
        conn.execute("UPDATE students SET mac_address=? WHERE id=?", (mac, student_id))
        conn.commit()

    # ── Find the latest active session ───────────────────────────
    active_session = conn.execute(
        "SELECT * FROM attendance_sessions WHERE active=1 ORDER BY id DESC LIMIT 1"
    ).fetchone()

    already_present = False
    session_active  = bool(active_session)

    if active_session:
        sid = active_session["id"]
        # Ensure record exists
        record = conn.execute(
            "SELECT * FROM attendance_records WHERE session_id=? AND student_id=?",
            (sid, student_id)
        ).fetchone()

        now_time = datetime.now().strftime("%H:%M:%S")
        if not record:
            conn.execute(
                "INSERT INTO attendance_records (session_id, student_id, status, marked_at, mac_address) "
                "VALUES (?,?,?,?,?)",
                (sid, student_id, "present", now_time, mac)
            )
            conn.commit()
        elif record["status"] == "absent" and not record["force_absent"]:
            conn.execute(
                "UPDATE attendance_records SET status='present', marked_at=?, mac_address=? "
                "WHERE session_id=? AND student_id=?",
                (now_time, mac, sid, student_id)
            )
            conn.commit()
        elif record["status"] == "present":
            already_present = True

    conn.close()

    return render_template("student.html",
                           student_name=student_name,
                           student_roll=student_roll,
                           session_active=session_active,
                           already_present=already_present)


# ─────────────────────────────────────────────────────────────────────────────
# API — SESSION MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/session/start", methods=["POST"])
@teacher_required
def start_session():
    data     = request.get_json(force=True)
    branch   = data.get("branch",   "CSE")
    section  = data.get("section",  "4B")
    semester = int(data.get("semester", 4))
    now      = datetime.now()

    conn   = get_db()
    cursor = conn.cursor()

    # Close any existing active session
    cursor.execute("UPDATE attendance_sessions SET active=0 WHERE active=1")

    # New session
    cursor.execute(
        "INSERT INTO attendance_sessions (teacher_id, branch, section, semester, date, time) "
        "VALUES (?,?,?,?,?,?)",
        (session["teacher_id"], branch, section, semester,
         now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"))
    )
    sess_id = cursor.lastrowid

    # Pre-insert absent for all students
    students = conn.execute(
        "SELECT id FROM students WHERE branch=? AND section=? AND semester=?",
        (branch, section, semester)
    ).fetchall()
    for s in students:
        cursor.execute(
            "INSERT OR IGNORE INTO attendance_records (session_id, student_id, status) VALUES (?,?,?)",
            (sess_id, s["id"], "absent")
        )

    conn.commit()
    conn.close()

    return jsonify({
        "session_id": sess_id,
        "date":       now.strftime("%Y-%m-%d"),
        "time":       now.strftime("%H:%M:%S"),
    })


@app.route("/api/session/stop", methods=["POST"])
@teacher_required
def stop_session():
    conn = get_db()
    conn.execute("UPDATE attendance_sessions SET active=0 WHERE active=1")
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# API — LIVE ATTENDANCE (teacher polls this every 3s)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/session/<int:session_id>/live")
@teacher_required
def live_status(session_id):
    conn = get_db()
    sess = conn.execute(
        "SELECT * FROM attendance_sessions WHERE id=?", (session_id,)
    ).fetchone()
    if not sess:
        conn.close()
        return jsonify({"error": "Session not found"}), 404

    records = conn.execute(
        """SELECT ar.id, ar.student_id, ar.status, ar.force_absent,
                  ar.marked_at, s.name, s.roll, s.mac_address AS student_mac
           FROM attendance_records ar
           JOIN students s ON ar.student_id = s.id
           WHERE ar.session_id=?
           ORDER BY s.name""",
        (session_id,)
    ).fetchall()

    # Scan LAN for active MAC addresses
    active_macs = scan_network()

    present = []
    absent  = []

    for r in records:
        smac       = r["student_mac"]
        on_network = bool(smac and smac.lower() in active_macs)

        # Auto-promote via ARP if not force-disconnected
        if on_network and r["status"] == "absent" and not r["force_absent"]:
            now_t = datetime.now().strftime("%H:%M:%S")
            conn.execute(
                "UPDATE attendance_records SET status='present', marked_at=? WHERE id=?",
                (now_t, r["id"])
            )
            conn.commit()
            status    = "present"
            marked_at = now_t
        else:
            status    = r["status"]
            marked_at = r["marked_at"]

        entry = {
            "id":        r["student_id"],
            "name":      r["name"],
            "roll":      r["roll"],
            "marked_at": marked_at,
            "on_network": on_network,
        }
        (present if status == "present" else absent).append(entry)

    conn.close()
    return jsonify({
        "present": present,
        "absent":  absent,
        "total":   len(records),
        "date":    sess["date"],
        "time":    sess["time"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# API — DISCONNECT (teacher marks someone absent manually)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/disconnect/<int:student_id>", methods=["POST"])
@teacher_required
def disconnect_student(student_id):
    data       = request.get_json(force=True) or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400

    conn = get_db()
    conn.execute(
        "UPDATE attendance_records "
        "SET status='absent', force_absent=1, marked_at=NULL "
        "WHERE session_id=? AND student_id=?",
        (session_id, student_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# API — EXPORT
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/session/<int:session_id>/export/csv")
@teacher_required
def export_csv(session_id):
    conn    = get_db()
    records = conn.execute(
        """SELECT s.roll, s.name, ar.status, ar.marked_at, ses.date
           FROM attendance_records ar
           JOIN students s ON ar.student_id=s.id
           JOIN attendance_sessions ses ON ar.session_id=ses.id
           WHERE ar.session_id=? ORDER BY s.name""",
        (session_id,)
    ).fetchall()
    conn.close()

    out = io.StringIO()
    w   = csv.writer(out)
    w.writerow(["Roll No", "Name", "Status", "Time Marked", "Date"])
    for r in records:
        w.writerow([r["roll"], r["name"], r["status"].upper(),
                    r["marked_at"] or "--", r["date"]])
    out.seek(0)
    resp = make_response(out.getvalue())
    resp.headers["Content-Type"]        = "text/csv"
    resp.headers["Content-Disposition"] = f"attachment; filename=attendance_{session_id}.csv"
    return resp


@app.route("/api/session/<int:session_id>/export/txt")
@teacher_required
def export_txt(session_id):
    conn    = get_db()
    sess    = conn.execute("SELECT * FROM attendance_sessions WHERE id=?", (session_id,)).fetchone()
    records = conn.execute(
        """SELECT s.roll, s.name, ar.status, ar.marked_at
           FROM attendance_records ar JOIN students s ON ar.student_id=s.id
           WHERE ar.session_id=? ORDER BY s.name""",
        (session_id,)
    ).fetchall()
    conn.close()

    lines = ["=" * 64, "  WIFINCE — Attendance Report", "=" * 64]
    if sess:
        lines += [
            f"  Session : {session_id}",
            f"  {sess['branch']}  |  {sess['section']}  |  Sem {sess['semester']}",
            f"  Date    : {sess['date']}  Started: {sess['time']}",
            "-" * 64,
            f"  {'ROLL':<16} {'NAME':<22} {'STATUS':<10} TIME",
            "-" * 64,
        ]
    for r in records:
        lines.append(f"  {r['roll']:<16} {r['name']:<22} {r['status'].upper():<10} {r['marked_at'] or '--'}")
    present = sum(1 for r in records if r["status"] == "present")
    lines += ["-"*64, f"  Present: {present}/{len(records)}", "="*64]

    resp = make_response("\n".join(lines))
    resp.headers["Content-Type"]        = "text/plain"
    resp.headers["Content-Disposition"] = f"attachment; filename=attendance_{session_id}.txt"
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

# Always init DB and seed on import (needed for gunicorn)
init_db()
seed_all()

if __name__ == "__main__":
    lan_ip = get_lan_ip()
    print("\n" + "=" * 50)
    print("  WIFINCE is running!")
    print(f"  Login Page   : http://localhost:5000/login")
    print(f"  Teacher      : http://localhost:5000/teacher")
    print(f"  Student Link : http://{lan_ip}:5000/login?role=student")
    print()
    print("  Default Teacher Login:")
    print("    ID       : teacher")
    print("    Password : wifince123")
    print("=" * 50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
