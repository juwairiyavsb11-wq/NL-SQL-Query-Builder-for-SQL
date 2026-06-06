"""
AskDB — Metadata Database Controller
Manages users, databases, query history, and saved queries.
"""

import os
import sqlite3
from datetime import datetime

METADATA_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database",
    "askdb_metadata.db"
)

def get_connection():
    """Get connection to the metadata database."""
    os.makedirs(os.path.dirname(METADATA_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(METADATA_DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initialize metadata database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # User Databases Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS databases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            table_count INTEGER DEFAULT 0,
            total_columns INTEGER DEFAULT 0,
            total_rows INTEGER DEFAULT 0,
            file_size INTEGER DEFAULT 0,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    # Query History Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            database_id INTEGER NOT NULL,
            nl_query TEXT NOT NULL,
            generated_sql TEXT NOT NULL,
            confidence REAL,
            row_count INTEGER,
            execution_time REAL,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(database_id) REFERENCES databases(id) ON DELETE CASCADE
        );
    """)

    # Saved Queries Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            database_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            nl_query TEXT NOT NULL,
            generated_sql TEXT NOT NULL,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(database_id) REFERENCES databases(id) ON DELETE CASCADE
        );
    """)

    conn.commit()
    conn.close()

# ──────────────────────────────────────────────────────────────────────
# User Operations
# ──────────────────────────────────────────────────────────────────────

def create_user(username, password_hash):
    """Create a new user. Returns the user ID or None if username exists."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username.strip(), password_hash)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_username(username):
    """Retrieve user dictionary by username."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE LOWER(username) = ?",
        (username.strip().lower(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id):
    """Retrieve user dictionary by ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def update_password(user_id, password_hash):
    """Update user's password hash."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (password_hash, user_id)
    )
    conn.commit()
    conn.close()

# ──────────────────────────────────────────────────────────────────────
# Database Operations
# ──────────────────────────────────────────────────────────────────────

def add_database(user_id, filename, original_name, table_count, total_columns, total_rows, file_size):
    """Register an uploaded database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO databases (
            user_id, filename, original_name, table_count, total_columns, total_rows, file_size
        ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, filename, original_name, table_count, total_columns, total_rows, file_size)
    )
    conn.commit()
    db_id = cursor.lastrowid
    conn.close()
    return db_id

def get_user_databases(user_id):
    """Get list of databases uploaded by a user."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM databases WHERE user_id = ? ORDER BY uploaded_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_database_by_id(user_id, database_id):
    """Get specific user database details."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM databases WHERE user_id = ? AND id = ?",
        (user_id, database_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def delete_database(user_id, database_id):
    """Delete database entry. Returns the filename of deleted database to clean up disk."""
    db_info = get_database_by_id(user_id, database_id)
    if not db_info:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM databases WHERE user_id = ? AND id = ?",
        (user_id, database_id)
    )
    conn.commit()
    conn.close()
    return db_info["filename"]

# ──────────────────────────────────────────────────────────────────────
# Query History Operations
# ──────────────────────────────────────────────────────────────────────

def add_history(user_id, database_id, nl_query, generated_sql, confidence, row_count, execution_time):
    """Log an executed query to history."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO query_history (
            user_id, database_id, nl_query, generated_sql, confidence, row_count, execution_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, database_id, nl_query, generated_sql, confidence, row_count, execution_time)
    )
    conn.commit()
    conn.close()

def get_history(user_id, limit=50):
    """Get history logs for a user, enriched with database name."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT h.*, d.original_name as database_name 
           FROM query_history h 
           JOIN databases d ON h.database_id = d.id 
           WHERE h.user_id = ? 
           ORDER BY h.executed_at DESC LIMIT ?""",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_history_item(user_id, history_id):
    """Delete a query history entry."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM query_history WHERE user_id = ? AND id = ?",
        (user_id, history_id)
    )
    conn.commit()
    conn.close()

def clear_history(user_id):
    """Clear query logs for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM query_history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ──────────────────────────────────────────────────────────────────────
# Saved Queries Operations
# ──────────────────────────────────────────────────────────────────────

def add_saved_query(user_id, database_id, name, nl_query, generated_sql):
    """Bookmark/Save a query."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO saved_queries (
            user_id, database_id, name, nl_query, generated_sql
        ) VALUES (?, ?, ?, ?, ?)""",
        (user_id, database_id, name.strip(), nl_query.strip(), generated_sql.strip())
    )
    conn.commit()
    conn.close()

def get_saved_queries(user_id):
    """Get saved queries for a user, enriched with database name."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT s.*, d.original_name as database_name 
           FROM saved_queries s 
           JOIN databases d ON s.database_id = d.id 
           WHERE s.user_id = ? 
           ORDER BY s.saved_at DESC""",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_saved_query(user_id, saved_id):
    """Delete a saved query."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM saved_queries WHERE user_id = ? AND id = ?",
        (user_id, saved_id)
    )
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    """Get statistics for the dashboard overview."""
    conn = get_connection()
    cursor = conn.cursor()
    
    db_count = cursor.execute("SELECT COUNT(*) FROM databases WHERE user_id = ?", (user_id,)).fetchone()[0]
    history_count = cursor.execute("SELECT COUNT(*) FROM query_history WHERE user_id = ?", (user_id,)).fetchone()[0]
    saved_count = cursor.execute("SELECT COUNT(*) FROM saved_queries WHERE user_id = ?", (user_id,)).fetchone()[0]
    
    conn.close()
    return {
        "databases": db_count,
        "history": history_count,
        "saved_queries": saved_count
    }
