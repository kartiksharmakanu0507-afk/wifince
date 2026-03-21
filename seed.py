"""
seed.py — Default teacher + CSE 4B Sem 4 students
"""
from database import get_db

# ── Default teacher credentials ──────────────────────────────
# Login: teacher_id = "teacher"  |  password = "wifince123"
TEACHERS = [
    ("teacher", "Prof. Sharma", "wifince123"),
]

# ── Students ──────────────────────────────────────────────────
STUDENTS = [
    ("Jay Kumar",       "JIETCSE079"),
    ("Jatin",           "JIETCSE080"),
    ("Jessica",         "JIETCSE081"),
    ("Joy",             "JIETCSE082"),
    ("Kanishk",         "JIETCSE083"),
    ("Kalpesh",         "JIETCSE084"),
    ("Karan",           "JIETCSE085"),
    ("Karan Purohit",   "JIETCSE086"),
    ("Kartik Gaur",     "JIETCSE087"),
    ("Kartik Sharma",   "JIETCSE088"),
    ("Kashish",         "JIETCSE089"),
    ("Kavita",          "JIETCSE090"),
    ("Khush Bhati",     "JIETCSE091"),
    ("Khush Jain",      "JIETCSE092"),
    ("Khushal Lakhani", "JIETCSE093"),
]


def seed_all():
    conn = get_db()

    # Teachers
    for tid, name, pwd in TEACHERS:
        exists = conn.execute("SELECT id FROM teachers WHERE teacher_id=?", (tid,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO teachers (teacher_id, name, password) VALUES (?,?,?)",
                (tid, name, pwd)
            )
    conn.commit()

    # Students
    count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    if count == 0:
        for name, roll in STUDENTS:
            conn.execute(
                "INSERT INTO students (name, roll, branch, section, semester) VALUES (?,?,?,?,?)",
                (name, roll, "CSE", "4B", 4)
            )
        conn.commit()
        print(f"[SEED] {len(STUDENTS)} students inserted.")
    else:
        print(f"[SEED] {count} students already in DB.")

    conn.close()
