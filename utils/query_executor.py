"""
AskDB — Query Executor
Safely executes SQL queries against SQLite databases with validation and metrics.
"""

import sqlite3
import time
import re


# SQL statements that are allowed
ALLOWED_KEYWORDS = {"SELECT", "WITH"}

# SQL statements that are BLOCKED
BLOCKED_KEYWORDS = {
    "DELETE", "DROP", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "RENAME", "ATTACH", "DETACH", "VACUUM",
    "REINDEX", "PRAGMA", "GRANT", "REVOKE", "COMMIT", "ROLLBACK",
    "SAVEPOINT", "RELEASE", "BEGIN", "END"
}


def validate_query(sql):
    """
    Validate that a SQL query is safe to execute.
    Only SELECT-based queries are allowed.
    Returns (is_valid, message).
    """
    if not sql or not sql.strip():
        return False, "Empty query"

    cleaned = re.sub(r"--[^\n]*", "", sql)       # remove line comments
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)  # remove block comments
    cleaned = cleaned.strip().upper()

    # Check first keyword
    first_word = cleaned.split()[0] if cleaned.split() else ""

    if first_word in BLOCKED_KEYWORDS:
        return False, f"Blocked operation: {first_word}. Only SELECT queries are allowed for safety."

    if first_word not in ALLOWED_KEYWORDS:
        return False, f"Unsupported operation: {first_word}. Only SELECT queries are allowed."

    # Check for dangerous keywords anywhere (could be injected via subqueries)
    for blocked in BLOCKED_KEYWORDS:
        # Look for the keyword as a standalone word (not inside strings)
        pattern = r"\b" + blocked + r"\b"
        # Remove string literals first
        no_strings = re.sub(r"'[^']*'", "", cleaned)
        if re.search(pattern, no_strings):
            return False, f"Query contains blocked keyword: {blocked}. Only read operations are allowed."

    # Check for multiple statements (semicolons)
    no_strings = re.sub(r"'[^']*'", "", cleaned)
    if ";" in no_strings.rstrip(";"):
        return False, "Multiple statements are not allowed. Please submit one query at a time."

    return True, "Query is safe to execute"


def execute_query(db_path, sql, timeout=10):
    """
    Execute a validated SQL query and return results with metrics.
    Returns a dict with columns, rows, execution_time, row_count, and status.
    """
    # Validate first
    is_valid, message = validate_query(sql)
    if not is_valid:
        return {
            "success": False,
            "error": message,
            "columns": [],
            "rows": [],
            "execution_time": 0,
            "row_count": 0
        }

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")  # Extra safety: read-only mode

        cursor = conn.cursor()

        start_time = time.time()
        cursor.execute(sql)
        rows_raw = cursor.fetchall()
        execution_time = round((time.time() - start_time) * 1000, 2)  # ms

        columns = [description[0] for description in cursor.description] if cursor.description else []

        # Convert rows to list of lists for JSON serialization
        rows = []
        for row in rows_raw:
            rows.append([row[i] for i in range(len(columns))])

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "execution_time": execution_time,
            "row_count": len(rows),
            "error": None
        }

    except sqlite3.OperationalError as e:
        return {
            "success": False,
            "error": f"SQL Error: {str(e)}",
            "columns": [],
            "rows": [],
            "execution_time": 0,
            "row_count": 0
        }
    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"Database Error: {str(e)}",
            "columns": [],
            "rows": [],
            "execution_time": 0,
            "row_count": 0
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected Error: {str(e)}",
            "columns": [],
            "rows": [],
            "execution_time": 0,
            "row_count": 0
        }
    finally:
        if conn:
            conn.close()
