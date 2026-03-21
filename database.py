"""
database.py — SQLite schema for WIFINCE
Tables: teachers, students, attendance_sessions, attendance_records
"""
import sqlite3

DB_PATH = "attendance.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS teachers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id  TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            password    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS students (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            roll          TEXT UNIQUE NOT NULL,
            branch        TEXT NOT NULL,
            section       TEXT NOT NULL,
            semester      INTEGER NOT NULL,
            mac_address   TEXT,
            registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            branch     TEXT NOT NULL,
            section    TEXT NOT NULL,
            semester   INTEGER NOT NULL,
            date       TEXT NOT NULL,
            time       TEXT NOT NULL,
            active     INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        );

        CREATE TABLE IF NOT EXISTS attendance_records (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER NOT NULL,
            student_id   INTEGER NOT NULL,
            status       TEXT NOT NULL DEFAULT 'absent',
            force_absent INTEGER NOT NULL DEFAULT 0,
            marked_at    DATETIME,
            mac_address  TEXT,
            FOREIGN KEY (session_id)  REFERENCES attendance_sessions(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE (session_id, student_id)
        );
    ''')
    conn.commit()
    conn.close()
    print("[DB] Tables ready.")
