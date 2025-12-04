"""Database module for job tracking with DuckDB."""

import os
import json
import duckdb
from pathlib import Path
from enum import Enum
from dotenv import load_dotenv


class JobStatus(str, Enum):
    """Status of a job application."""
    INTERESTED = "interested"      # Saved, not yet applied
    APPLIED = "applied"            # Application submitted
    INTERVIEWING = "interviewing"  # In interview process
    OFFERED = "offered"            # Received an offer
    REJECTED = "rejected"          # Application rejected
    WITHDRAWN = "withdrawn"        # Withdrew application
    GHOSTED = "ghosted"            # No response after applying


class EventType(str, Enum):
    """Types of events in the job timeline."""
    ADDED = "added"                # Job was added to tracker
    APPLIED = "applied"            # Submitted application
    RESPONSE = "response"          # Received a response
    INTERVIEW = "interview"        # Had an interview
    OFFER = "offer"                # Received an offer
    REJECTED = "rejected"          # Was rejected
    WITHDRAWN = "withdrawn"        # Withdrew application
    NOTE = "note"                  # General note


def get_db_path() -> Path:
    """Get the path to the database file.

    Priority:
    1. JOB_LOG_DB_PATH environment variable (shell or .env file)
    2. Default: ~/.job-log/jobs.duckdb

    The .env file is loaded from ~/.job-log/.env
    """
    # Load .env file from ~/.job-log/.env
    env_file = Path.home() / ".job-log" / ".env"
    load_dotenv(env_file)

    # Check environment variable (from shell or .env)
    if custom_path := os.environ.get("JOB_LOG_DB_PATH"):
        data_dir = Path(os.path.expandvars(os.path.expanduser(custom_path)))
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "jobs.duckdb"

    # Default
    data_dir = Path.home() / ".job-log"
    data_dir.mkdir(exist_ok=True)
    return data_dir / "jobs.duckdb"


def get_connection() -> duckdb.DuckDBPyConnection:
    """Get a connection to the database."""
    db_path = get_db_path()
    return duckdb.connect(str(db_path))


def init_db() -> None:
    """Initialize the database schema."""
    conn = get_connection()

    # Create jobs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY,
            company VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            posting_url VARCHAR,
            application_url VARCHAR,
            location VARCHAR,
            salary VARCHAR,
            description TEXT,
            status VARCHAR DEFAULT 'interested',
            source VARCHAR DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migration: Add source column if it doesn't exist (for existing databases)
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN source VARCHAR DEFAULT 'manual'")
    except duckdb.CatalogException:
        pass  # Column already exists

    # Create sequence for job IDs if it doesn't exist
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS jobs_id_seq START 1
    """)

    # Create events table for timeline tracking
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            job_id INTEGER NOT NULL,
            event_type VARCHAR NOT NULL,
            event_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            resume_path VARCHAR,
            cover_letter_path VARCHAR,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)

    # Create sequence for event IDs
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS events_id_seq START 1
    """)

    conn.close()


def add_job(
    company: str,
    title: str,
    posting_url: str | None = None,
    location: str | None = None,
    salary: str | None = None,
    description: str | None = None,
    source: str = "manual",
) -> int:
    """Add a new job to track. Returns the job ID.

    Args:
        source: How the job was added - 'manual' (default) or 'ai' (via AI scan)
    """
    conn = get_connection()

    job_id = conn.execute("SELECT nextval('jobs_id_seq')").fetchone()[0]

    conn.execute("""
        INSERT INTO jobs (id, company, title, posting_url, location, salary, description, status, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [job_id, company, title, posting_url, location, salary, description, JobStatus.INTERESTED.value, source])

    # Add initial event
    event_id = conn.execute("SELECT nextval('events_id_seq')").fetchone()[0]
    conn.execute("""
        INSERT INTO events (id, job_id, event_type, notes)
        VALUES (?, ?, ?, ?)
    """, [event_id, job_id, EventType.ADDED.value, f"Added {title} at {company}"])

    conn.close()
    return job_id


def apply_to_job(
    job_id: int,
    resume_path: str | None = None,
    cover_letter_path: str | None = None,
    application_url: str | None = None,
    notes: str | None = None,
    applied_date: str | None = None,
) -> None:
    """Record that you applied to a job."""
    conn = get_connection()

    # Update job status and optionally application_url
    if application_url:
        conn.execute("""
            UPDATE jobs
            SET status = ?, application_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [JobStatus.APPLIED.value, application_url, job_id])
    else:
        conn.execute("""
            UPDATE jobs
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [JobStatus.APPLIED.value, job_id])

    # Add event
    event_id = conn.execute("SELECT nextval('events_id_seq')").fetchone()[0]
    if applied_date:
        conn.execute("""
            INSERT INTO events (id, job_id, event_type, event_date, notes, resume_path, cover_letter_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [event_id, job_id, EventType.APPLIED.value, applied_date, notes, resume_path, cover_letter_path])
    else:
        conn.execute("""
            INSERT INTO events (id, job_id, event_type, notes, resume_path, cover_letter_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [event_id, job_id, EventType.APPLIED.value, notes, resume_path, cover_letter_path])

    conn.close()


def add_response(
    job_id: int,
    interested: bool,
    notes: str | None = None,
) -> None:
    """Record a response from a company."""
    conn = get_connection()

    if interested:
        new_status = JobStatus.INTERVIEWING.value
        event_type = EventType.RESPONSE.value
    else:
        new_status = JobStatus.REJECTED.value
        event_type = EventType.REJECTED.value

    # Update job status
    conn.execute("""
        UPDATE jobs
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, [new_status, job_id])

    # Add event
    event_id = conn.execute("SELECT nextval('events_id_seq')").fetchone()[0]
    conn.execute("""
        INSERT INTO events (id, job_id, event_type, notes)
        VALUES (?, ?, ?, ?)
    """, [event_id, job_id, event_type, notes])

    conn.close()


def add_interview(
    job_id: int,
    notes: str | None = None,
) -> None:
    """Record an interview."""
    conn = get_connection()

    # Ensure status is interviewing
    conn.execute("""
        UPDATE jobs
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, [JobStatus.INTERVIEWING.value, job_id])

    # Add event
    event_id = conn.execute("SELECT nextval('events_id_seq')").fetchone()[0]
    conn.execute("""
        INSERT INTO events (id, job_id, event_type, notes)
        VALUES (?, ?, ?, ?)
    """, [event_id, job_id, EventType.INTERVIEW.value, notes])

    conn.close()


def update_status(job_id: int, status: JobStatus, notes: str | None = None) -> None:
    """Update the status of a job."""
    conn = get_connection()

    conn.execute("""
        UPDATE jobs
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, [status.value, job_id])

    # Map status to event type
    event_type_map = {
        JobStatus.OFFERED: EventType.OFFER,
        JobStatus.REJECTED: EventType.REJECTED,
        JobStatus.WITHDRAWN: EventType.WITHDRAWN,
        JobStatus.GHOSTED: EventType.NOTE,
    }
    event_type = event_type_map.get(status, EventType.NOTE)

    event_id = conn.execute("SELECT nextval('events_id_seq')").fetchone()[0]
    conn.execute("""
        INSERT INTO events (id, job_id, event_type, notes)
        VALUES (?, ?, ?, ?)
    """, [event_id, job_id, event_type.value, notes or f"Status changed to {status.value}"])

    conn.close()


def set_application_url(job_id: int, application_url: str) -> None:
    """Set the application tracking URL for a job."""
    conn = get_connection()
    conn.execute("""
        UPDATE jobs
        SET application_url = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, [application_url, job_id])
    conn.close()


def delete_job(job_id: int) -> bool:
    """Delete a job and its events. Returns True if job existed."""
    conn = get_connection()

    # Check if job exists
    exists = conn.execute("SELECT 1 FROM jobs WHERE id = ?", [job_id]).fetchone()
    if not exists:
        conn.close()
        return False

    # Delete events first (foreign key)
    conn.execute("DELETE FROM events WHERE job_id = ?", [job_id])
    conn.execute("DELETE FROM jobs WHERE id = ?", [job_id])
    conn.close()
    return True


def update_applied_date(job_id: int, applied_date: str) -> bool:
    """Update the applied date for a job. Returns True if an applied event existed."""
    conn = get_connection()

    # Check if applied event exists
    exists = conn.execute("""
        SELECT 1 FROM events WHERE job_id = ? AND event_type = 'applied'
    """, [job_id]).fetchone()

    if not exists:
        conn.close()
        return False

    conn.execute("""
        UPDATE events
        SET event_date = ?
        WHERE job_id = ? AND event_type = 'applied'
    """, [applied_date, job_id])
    conn.close()
    return True


def update_job(
    job_id: int,
    location: str | None = None,
    posting_url: str | None = None,
) -> None:
    """Update job fields."""
    conn = get_connection()

    if location is not None:
        conn.execute("""
            UPDATE jobs
            SET location = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [location, job_id])

    if posting_url is not None:
        conn.execute("""
            UPDATE jobs
            SET posting_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [posting_url, job_id])

    conn.close()


def search_jobs(
    company: str | None = None,
    title: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """
    Search jobs by company name and/or title (fuzzy match).

    Args:
        company: Company name to search for (uses ILIKE for fuzzy matching)
        title: Job title to search for (uses ILIKE for fuzzy matching)
        status: Filter by status

    Returns:
        List of matching job dictionaries
    """
    conn = get_connection()

    query = """
        SELECT id, company, title, posting_url, application_url, location,
               salary, description, status, source, created_at, updated_at
        FROM jobs
        WHERE 1=1
    """
    params = []

    if company:
        query += " AND company ILIKE ?"
        params.append(f"%{company}%")

    if title:
        query += " AND title ILIKE ?"
        params.append(f"%{title}%")

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY updated_at DESC"

    results = conn.execute(query, params).fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "company": r[1],
            "title": r[2],
            "posting_url": r[3],
            "application_url": r[4],
            "location": r[5],
            "salary": r[6],
            "description": r[7],
            "status": r[8],
            "source": r[9],
            "created_at": r[10],
            "updated_at": r[11],
        }
        for r in results
    ]


def get_job(job_id: int) -> dict | None:
    """Get a single job by ID."""
    conn = get_connection()
    result = conn.execute("""
        SELECT id, company, title, posting_url, application_url, location, salary, description, status, source, created_at, updated_at
        FROM jobs WHERE id = ?
    """, [job_id]).fetchone()
    conn.close()

    if result is None:
        return None

    return {
        "id": result[0],
        "company": result[1],
        "title": result[2],
        "posting_url": result[3],
        "application_url": result[4],
        "location": result[5],
        "salary": result[6],
        "description": result[7],
        "status": result[8],
        "source": result[9],
        "created_at": result[10],
        "updated_at": result[11],
    }


def get_events(job_id: int) -> list[dict]:
    """Get all events for a job."""
    conn = get_connection()
    results = conn.execute("""
        SELECT id, job_id, event_type, event_date, notes, resume_path, cover_letter_path
        FROM events
        WHERE job_id = ?
        ORDER BY event_date ASC
    """, [job_id]).fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "job_id": r[1],
            "event_type": r[2],
            "event_date": r[3],
            "notes": r[4],
            "resume_path": r[5],
            "cover_letter_path": r[6],
        }
        for r in results
    ]


def get_activity(days: int = 7) -> dict:
    """Get activity summary for the last N days.

    Returns:
        Dictionary with:
        - jobs_added: list of jobs added in the period
        - applications: list of jobs applied to in the period
        - events: list of all events in the period (excluding 'added')
        - summary: counts by event type
    """
    conn = get_connection()

    # Get jobs added in the period
    jobs_added = conn.execute(f"""
        SELECT id, company, title, location, status, source, created_at
        FROM jobs
        WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '{days}' DAY
        ORDER BY created_at DESC
    """).fetchall()

    # Get all events in the period
    events = conn.execute(f"""
        SELECT e.id, e.job_id, e.event_type, e.event_date, e.notes,
               j.company, j.title
        FROM events e
        JOIN jobs j ON e.job_id = j.id
        WHERE e.event_date >= CURRENT_TIMESTAMP - INTERVAL '{days}' DAY
        ORDER BY e.event_date DESC
    """).fetchall()

    conn.close()

    # Build summary counts
    summary = {}
    for event in events:
        event_type = event[2]
        summary[event_type] = summary.get(event_type, 0) + 1

    return {
        "jobs_added": [
            {
                "id": r[0],
                "company": r[1],
                "title": r[2],
                "location": r[3],
                "status": r[4],
                "source": r[5],
                "created_at": r[6],
            }
            for r in jobs_added
        ],
        "events": [
            {
                "id": r[0],
                "job_id": r[1],
                "event_type": r[2],
                "event_date": r[3],
                "notes": r[4],
                "company": r[5],
                "title": r[6],
            }
            for r in events
        ],
        "summary": summary,
    }


def list_jobs(status: str | None = None) -> list[dict]:
    """List all jobs, optionally filtered by status."""
    conn = get_connection()

    # Join with events to get the applied date
    if status:
        results = conn.execute("""
            SELECT j.id, j.company, j.title, j.posting_url, j.application_url, j.location,
                   j.salary, j.description, j.status, j.source, j.created_at, j.updated_at,
                   (SELECT event_date FROM events WHERE job_id = j.id AND event_type = 'applied' LIMIT 1) as applied_at
            FROM jobs j
            WHERE j.status = ?
            ORDER BY j.updated_at DESC
        """, [status]).fetchall()
    else:
        results = conn.execute("""
            SELECT j.id, j.company, j.title, j.posting_url, j.application_url, j.location,
                   j.salary, j.description, j.status, j.source, j.created_at, j.updated_at,
                   (SELECT event_date FROM events WHERE job_id = j.id AND event_type = 'applied' LIMIT 1) as applied_at
            FROM jobs j
            ORDER BY j.updated_at DESC
        """).fetchall()

    conn.close()

    return [
        {
            "id": r[0],
            "company": r[1],
            "title": r[2],
            "posting_url": r[3],
            "application_url": r[4],
            "location": r[5],
            "salary": r[6],
            "description": r[7],
            "status": r[8],
            "source": r[9],
            "created_at": r[10],
            "updated_at": r[11],
            "applied_at": r[12],
        }
        for r in results
    ]
