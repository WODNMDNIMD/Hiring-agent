from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_DB_PATH = Path("data/recruitflow.db")


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                jd TEXT NOT NULL,
                owner TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                current_city TEXT,
                education TEXT,
                school TEXT,
                major TEXT,
                experience_years REAL,
                latest_company TEXT,
                latest_title TEXT,
                skills TEXT,
                job_status TEXT,
                expected_salary TEXT,
                arrival_time TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                stage TEXT NOT NULL,
                score INTEGER,
                recommendation_level TEXT,
                recommendation_text TEXT,
                matched_points TEXT,
                risk_points TEXT,
                owner TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(candidate_id) REFERENCES candidates(id),
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );

            CREATE TABLE IF NOT EXISTS recruitment_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER,
                event_type TEXT NOT NULL,
                raw_content TEXT,
                parsed_content TEXT,
                old_stage TEXT,
                new_stage TEXT,
                confidence REAL,
                status TEXT DEFAULT 'confirmed',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(application_id) REFERENCES applications(id)
            );

            CREATE TABLE IF NOT EXISTS integration_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                integration_type TEXT NOT NULL,
                request_data TEXT,
                response_data TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(event_id) REFERENCES recruitment_events(id)
            );
            """
        )


def add_job(title: str, jd: str, owner: str | None = None, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    with connect(db_path) as conn:
        cur = conn.execute("INSERT INTO jobs(title, jd, owner) VALUES (?, ?, ?)", (title, jd, owner))
        return int(cur.lastrowid)


def list_jobs(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    with connect(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM jobs ORDER BY created_at DESC", conn)


def find_candidate(name: str, phone: str | None = None, email: str | None = None, db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Row | None:
    with connect(db_path) as conn:
        if phone:
            row = conn.execute("SELECT * FROM candidates WHERE phone = ? LIMIT 1", (phone,)).fetchone()
            if row:
                return row
        if email:
            row = conn.execute("SELECT * FROM candidates WHERE email = ? LIMIT 1", (email,)).fetchone()
            if row:
                return row
        return conn.execute("SELECT * FROM candidates WHERE name = ? ORDER BY updated_at DESC LIMIT 1", (name,)).fetchone()


def upsert_candidate(profile: dict[str, Any], db_path: str | Path = DEFAULT_DB_PATH) -> int:
    existing = find_candidate(profile.get("name", ""), profile.get("phone"), profile.get("email"), db_path)
    skills = json.dumps(profile.get("skills", []), ensure_ascii=False)
    values = (
        profile.get("name") or "未知候选人",
        profile.get("phone"),
        profile.get("email"),
        profile.get("current_city"),
        profile.get("education"),
        profile.get("school"),
        profile.get("major"),
        profile.get("experience_years"),
        profile.get("latest_company"),
        profile.get("latest_title"),
        skills,
        profile.get("job_status"),
        profile.get("expected_salary"),
        profile.get("arrival_time"),
    )
    with connect(db_path) as conn:
        if existing:
            conn.execute(
                """
                UPDATE candidates SET
                    name=?, phone=?, email=?, current_city=?, education=?, school=?, major=?,
                    experience_years=?, latest_company=?, latest_title=?, skills=?, job_status=?,
                    expected_salary=?, arrival_time=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                values + (existing["id"],),
            )
            return int(existing["id"])
        cur = conn.execute(
            """
            INSERT INTO candidates(
                name, phone, email, current_city, education, school, major, experience_years,
                latest_company, latest_title, skills, job_status, expected_salary, arrival_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        return int(cur.lastrowid)


def create_application(
    candidate_id: int,
    job_id: int,
    stage: str,
    match: dict[str, Any],
    owner: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    with connect(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM applications WHERE candidate_id=? AND job_id=? LIMIT 1",
            (candidate_id, job_id),
        ).fetchone()
        payload = (
            stage,
            match.get("score"),
            match.get("recommendation_level"),
            match.get("recommendation_text"),
            json.dumps(match.get("matched_points", []), ensure_ascii=False),
            json.dumps(match.get("risk_points", []), ensure_ascii=False),
            owner,
        )
        if existing:
            conn.execute(
                """
                UPDATE applications SET stage=?, score=?, recommendation_level=?, recommendation_text=?,
                    matched_points=?, risk_points=?, owner=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                payload + (existing["id"],),
            )
            return int(existing["id"])
        cur = conn.execute(
            """
            INSERT INTO applications(
                candidate_id, job_id, stage, score, recommendation_level, recommendation_text,
                matched_points, risk_points, owner
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (candidate_id, job_id) + payload,
        )
        return int(cur.lastrowid)


def update_application_stage(application_id: int, new_stage: str, db_path: str | Path = DEFAULT_DB_PATH) -> str:
    with connect(db_path) as conn:
        row = conn.execute("SELECT stage FROM applications WHERE id=?", (application_id,)).fetchone()
        old_stage = row["stage"] if row else ""
        conn.execute(
            "UPDATE applications SET stage=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (new_stage, application_id),
        )
        return old_stage


def add_event(
    application_id: int | None,
    event_type: str,
    raw_content: str | None,
    parsed_content: dict[str, Any] | None,
    old_stage: str | None = None,
    new_stage: str | None = None,
    confidence: float | None = None,
    status: str = "confirmed",
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO recruitment_events(
                application_id, event_type, raw_content, parsed_content, old_stage, new_stage,
                confidence, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                event_type,
                raw_content,
                json.dumps(parsed_content or {}, ensure_ascii=False),
                old_stage,
                new_stage,
                confidence,
                status,
            ),
        )
        return int(cur.lastrowid)


def add_integration_log(
    integration_type: str,
    status: str,
    request_data: dict[str, Any] | None = None,
    response_data: dict[str, Any] | None = None,
    error_message: str | None = None,
    event_id: int | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO integration_logs(event_id, integration_type, request_data, response_data, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                integration_type,
                json.dumps(request_data or {}, ensure_ascii=False),
                json.dumps(response_data or {}, ensure_ascii=False),
                status,
                error_message,
            ),
        )


def applications_view(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    with connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT
                a.id AS application_id,
                c.name,
                c.phone,
                c.email,
                c.education,
                c.school,
                c.experience_years,
                c.expected_salary,
                j.title AS job_title,
                a.stage,
                a.score,
                a.recommendation_level,
                a.owner,
                a.updated_at
            FROM applications a
            JOIN candidates c ON c.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            ORDER BY a.updated_at DESC
            """,
            conn,
        )


def events_view(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    with connect(db_path) as conn:
        return pd.read_sql_query(
            "SELECT * FROM recruitment_events ORDER BY created_at DESC LIMIT 100",
            conn,
        )

