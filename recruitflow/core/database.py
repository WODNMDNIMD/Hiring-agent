from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from .models import IntegrationLogCreate, RecruitmentEventCreate


DEFAULT_DB_PATH = Path("data/recruitflow.db")


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _json_dumps(data: dict[str, Any] | list[Any] | None) -> str:
    return json.dumps(data or {}, ensure_ascii=False)


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
                candidate_id INTEGER,
                job_id INTEGER,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'system',
                title TEXT,
                raw_content TEXT,
                parsed_content TEXT,
                payload TEXT,
                old_stage TEXT,
                new_stage TEXT,
                confidence REAL,
                status TEXT DEFAULT 'confirmed',
                actor TEXT,
                confirmed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(candidate_id) REFERENCES candidates(id),
                FOREIGN KEY(job_id) REFERENCES jobs(id),
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
        _migrate_event_tables(conn)


def _migrate_event_tables(conn: sqlite3.Connection) -> None:
    event_columns = {
        "candidate_id": "INTEGER REFERENCES candidates(id)",
        "job_id": "INTEGER REFERENCES jobs(id)",
        "source": "TEXT NOT NULL DEFAULT 'system'",
        "title": "TEXT",
        "payload": "TEXT",
        "actor": "TEXT",
        "confirmed_at": "TEXT",
        "updated_at": "TEXT",
    }
    _ensure_columns(conn, "recruitment_events", event_columns)
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_recruitment_events_application_id
            ON recruitment_events(application_id);
        CREATE INDEX IF NOT EXISTS idx_recruitment_events_candidate_id
            ON recruitment_events(candidate_id);
        CREATE INDEX IF NOT EXISTS idx_recruitment_events_job_id
            ON recruitment_events(job_id);
        CREATE INDEX IF NOT EXISTS idx_recruitment_events_type_status
            ON recruitment_events(event_type, status);
        CREATE INDEX IF NOT EXISTS idx_recruitment_events_created_at
            ON recruitment_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_integration_logs_event_id
            ON integration_logs(event_id);
        CREATE INDEX IF NOT EXISTS idx_integration_logs_type_status
            ON integration_logs(integration_type, status);
        CREATE INDEX IF NOT EXISTS idx_integration_logs_created_at
            ON integration_logs(created_at);
        """
    )


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    if table == "recruitment_events":
        conn.execute("UPDATE recruitment_events SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)")


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


def _application_links(conn: sqlite3.Connection, application_id: int | None) -> tuple[int | None, int | None]:
    if application_id is None:
        return None, None
    row = conn.execute(
        "SELECT candidate_id, job_id FROM applications WHERE id=?",
        (application_id,),
    ).fetchone()
    if not row:
        return None, None
    return int(row["candidate_id"]), int(row["job_id"])


def add_event(
    application_id: int | None,
    event_type: str,
    raw_content: str | None,
    parsed_content: dict[str, Any] | None,
    old_stage: str | None = None,
    new_stage: str | None = None,
    confidence: float | None = None,
    status: str = "confirmed",
    candidate_id: int | None = None,
    job_id: int | None = None,
    source: str = "system",
    title: str | None = None,
    payload: dict[str, Any] | None = None,
    actor: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    with connect(db_path) as conn:
        inferred_candidate_id, inferred_job_id = _application_links(conn, application_id)
        event = RecruitmentEventCreate(
            application_id=application_id,
            candidate_id=candidate_id or inferred_candidate_id,
            job_id=job_id or inferred_job_id,
            event_type=event_type,
            source=source,
            title=title,
            raw_content=raw_content,
            parsed_content=parsed_content or {},
            payload=payload or {},
            old_stage=old_stage,
            new_stage=new_stage,
            confidence=confidence,
            status=status,
            actor=actor,
        )
        cur = conn.execute(
            """
            INSERT INTO recruitment_events(
                application_id, candidate_id, job_id, event_type, source, title, raw_content,
                parsed_content, payload, old_stage, new_stage, confidence, status, actor,
                confirmed_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'confirmed' THEN CURRENT_TIMESTAMP ELSE NULL END, CURRENT_TIMESTAMP)
            """,
            (
                event.application_id,
                event.candidate_id,
                event.job_id,
                event.event_type,
                event.source,
                event.title,
                event.raw_content,
                _json_dumps(event.parsed_content),
                _json_dumps(event.payload),
                event.old_stage,
                event.new_stage,
                event.confidence,
                event.status,
                event.actor,
                event.status,
            ),
        )
        return int(cur.lastrowid)


def create_recruitment_event(event: RecruitmentEventCreate, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    return add_event(
        application_id=event.application_id,
        event_type=event.event_type,
        raw_content=event.raw_content,
        parsed_content=event.parsed_content,
        old_stage=event.old_stage,
        new_stage=event.new_stage,
        confidence=event.confidence,
        status=event.status,
        candidate_id=event.candidate_id,
        job_id=event.job_id,
        source=event.source,
        title=event.title,
        payload=event.payload,
        actor=event.actor,
        db_path=db_path,
    )


def mark_event_confirmed(
    event_id: int,
    payload_patch: dict[str, Any] | None = None,
    actor: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> bool:
    with connect(db_path) as conn:
        row = conn.execute("SELECT payload FROM recruitment_events WHERE id=?", (event_id,)).fetchone()
        if not row:
            return False
        payload = json.loads(row["payload"] or "{}")
        if payload_patch:
            payload.update(payload_patch)
        cur = conn.execute(
            """
            UPDATE recruitment_events
            SET status='confirmed', payload=?, actor=COALESCE(?, actor),
                confirmed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (_json_dumps(payload), actor, event_id),
        )
        return cur.rowcount > 0


def add_integration_log(
    integration_type: str,
    status: str,
    request_data: dict[str, Any] | None = None,
    response_data: dict[str, Any] | None = None,
    error_message: str | None = None,
    event_id: int | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    log = IntegrationLogCreate(
        integration_type=integration_type,
        status=status,
        request_data=request_data or {},
        response_data=response_data or {},
        error_message=error_message,
        event_id=event_id,
    )
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO integration_logs(event_id, integration_type, request_data, response_data, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                log.event_id,
                log.integration_type,
                _json_dumps(log.request_data),
                _json_dumps(log.response_data),
                log.status,
                log.error_message,
            ),
        )
        return int(cur.lastrowid)


def create_integration_log(log: IntegrationLogCreate, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    return add_integration_log(
        integration_type=log.integration_type,
        status=log.status,
        request_data=log.request_data,
        response_data=log.response_data,
        error_message=log.error_message,
        event_id=log.event_id,
        db_path=db_path,
    )


def list_recent_events(
    limit: int = 100,
    application_id: int | None = None,
    candidate_id: int | None = None,
    job_id: int | None = None,
    status: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    clauses: list[str] = []
    params: list[Any] = []
    if application_id is not None:
        clauses.append("application_id = ?")
        params.append(application_id)
    if candidate_id is not None:
        clauses.append("candidate_id = ?")
        params.append(candidate_id)
    if job_id is not None:
        clauses.append("job_id = ?")
        params.append(job_id)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM recruitment_events
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            params + [limit],
        ).fetchall()
    return [_row_to_event_dict(row) for row in rows]


def _row_to_event_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    for key in ("parsed_content", "payload"):
        try:
            item[key] = json.loads(item.get(key) or "{}")
        except json.JSONDecodeError:
            item[key] = {}
    return item


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
            """
            SELECT
                e.id,
                e.event_type,
                e.status,
                e.source,
                e.title,
                e.application_id,
                c.name AS candidate_name,
                j.title AS job_title,
                e.old_stage,
                e.new_stage,
                e.confidence,
                e.actor,
                e.confirmed_at,
                e.created_at
            FROM recruitment_events e
            LEFT JOIN candidates c ON c.id = e.candidate_id
            LEFT JOIN jobs j ON j.id = e.job_id
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 100
            """,
            conn,
        )


def integration_logs_view(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    with connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT
                id,
                event_id,
                integration_type,
                status,
                error_message,
                request_data,
                response_data,
                created_at
            FROM integration_logs
            ORDER BY created_at DESC, id DESC
            LIMIT 100
            """,
            conn,
        )
