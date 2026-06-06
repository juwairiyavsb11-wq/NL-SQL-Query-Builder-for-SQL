"""
AskDB — Flask Application
AI-powered Natural Language to SQL Query Builder.
"""

import os
import io
import csv
import shutil
import time
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from utils.schema_reader import get_schema, get_table_sample, get_database_insights
from utils.query_generator import generate_query, generate_suggestions
from utils.query_executor import execute_query, validate_query
from utils.metadata_db import (
    init_db, create_user, get_user_by_username, get_user_by_id, update_password,
    add_database, get_user_databases, get_database_by_id, delete_database,
    add_history, get_history, delete_history_item, clear_history,
    add_saved_query, get_saved_queries, delete_saved_query, get_user_stats
)

app = Flask(__name__)
app.secret_key = "askdb-premium-saas-secret-key-2026"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload

DATABASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database")
os.makedirs(DATABASE_DIR, exist_ok=True)

# Initialize Metadata Database
init_db()

ALLOWED_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}


def login_required(f):
    """Decorator to protect routes requiring authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def _get_db_path():
    """Get the current database path from session or default user DB."""
    user_id = session.get("user_id")
    if not user_id:
        return None

    active_db_id = session.get("active_db_id")
    if active_db_id:
        db_info = get_database_by_id(user_id, active_db_id)
        if db_info:
            path = os.path.join(DATABASE_DIR, f"user_{user_id}", db_info["filename"])
            if os.path.exists(path):
                return path

    # Fallback to the first database uploaded by this user
    dbs = get_user_databases(user_id)
    if dbs:
        db_info = dbs[0]
        session["active_db_id"] = db_info["id"]
        session["active_db_name"] = db_info["original_name"]
        path = os.path.join(DATABASE_DIR, f"user_{user_id}", db_info["filename"])
        if os.path.exists(path):
            return path

    return None


# ──────────────────────────────────────────────────────────────────────
# Page Routes (SaaS)
# ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the landing page."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter both username and password.", "error")
            return render_template("login.html")

        user = get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Handle user signup and seed sample database."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not password or not confirm_password:
            flash("All fields are required.", "error")
            return render_template("signup.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("signup.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("signup.html")

        user = get_user_by_username(username)
        if user:
            flash("Username already exists.", "error")
            return render_template("signup.html")

        # Create user
        hashed_password = generate_password_hash(password)
        user_id = create_user(username, hashed_password)

        if user_id:
            # Provision user-isolated directory
            user_db_dir = os.path.join(DATABASE_DIR, f"user_{user_id}")
            os.makedirs(user_db_dir, exist_ok=True)

            # Seed sample database
            src_sample = os.path.join(DATABASE_DIR, "ecommerce_sample.db")
            dest_sample = os.path.join(user_db_dir, "ecommerce_sample.db")

            if os.path.exists(src_sample):
                shutil.copy2(src_sample, dest_sample)
                try:
                    schema = get_schema(dest_sample)
                    add_database(
                        user_id=user_id,
                        filename="ecommerce_sample.db",
                        original_name="E-Commerce Sample Database",
                        table_count=schema["table_count"],
                        total_columns=schema["total_columns"],
                        total_rows=schema["total_rows"],
                        file_size=os.path.getsize(dest_sample)
                    )
                except Exception as e:
                    print("Failed to auto-seed database schema:", str(e))

            # Automatically login
            session["user_id"] = user_id
            session["username"] = username
            flash("Account created successfully! We pre-loaded a sample database for you.", "success")
            return redirect(url_for("overview"))
        else:
            flash("An error occurred during account creation.", "error")

    return render_template("signup.html")


@app.route("/logout")
def logout():
    """Log the user out."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/overview")
@login_required
def overview():
    """Render SaaS Overview."""
    user_id = session["user_id"]
    stats = get_user_stats(user_id)
    databases = get_user_databases(user_id)[:3]
    history = get_history(user_id, limit=5)
    saved = get_saved_queries(user_id)[:5]

    return render_template(
        "overview.html",
        stats=stats,
        databases=databases,
        history=history,
        saved_queries=saved
    )


@app.route("/dashboard")
def dashboard():
    """Redirect dashboard path for compatibility."""
    return redirect(url_for("overview"))


@app.route("/databases")
@login_required
def databases_page():
    """Render Databases list and upload page with analytics."""
    user_id = session["user_id"]
    dbs = get_user_databases(user_id)
    
    # Calculate stats for widgets
    total_dbs = len(dbs)
    stats = get_user_stats(user_id)
    total_queries = stats["history"]
    
    # Get most queried database (previously most used)
    most_queried_db = "None"
    try:
        from utils.metadata_db import get_connection
        conn = get_connection()
        row = conn.execute(
            """SELECT d.original_name, COUNT(*) as cnt 
               FROM query_history h 
               JOIN databases d ON h.database_id = d.id 
               WHERE h.user_id = ? 
               GROUP BY h.database_id 
               ORDER BY cnt DESC LIMIT 1""",
            (user_id,)
        ).fetchone()
        conn.close()
        if row:
            most_queried_db = row["original_name"]
    except Exception as e:
        print("Failed to calculate most queried DB:", str(e))
        
    # Get recently opened database (most recently queried, fallback to most recently uploaded)
    recently_opened_db = "None"
    try:
        from utils.metadata_db import get_connection
        conn = get_connection()
        row_recent = conn.execute(
            """SELECT d.original_name 
               FROM query_history h 
               JOIN databases d ON h.database_id = d.id 
               WHERE h.user_id = ? 
               ORDER BY h.executed_at DESC LIMIT 1""",
            (user_id,)
        ).fetchone()
        conn.close()
        if row_recent:
            recently_opened_db = row_recent["original_name"]
        elif dbs:
            recently_opened_db = dbs[0]["original_name"]
    except Exception as e:
        print("Failed to calculate recently opened DB:", str(e))
        
    db_stats = {
        "total": total_dbs,
        "queries": total_queries,
        "most_queried": most_queried_db,
        "recently_opened": recently_opened_db
    }
    
    # Calculate last_opened for each database card
    try:
        from utils.metadata_db import get_connection
        conn = get_connection()
        for db in dbs:
            row_last = conn.execute(
                "SELECT executed_at FROM query_history WHERE database_id = ? ORDER BY executed_at DESC LIMIT 1",
                (db["id"],)
            ).fetchone()
            if row_last:
                db["last_opened"] = row_last["executed_at"]
            else:
                db["last_opened"] = "Never"
        conn.close()
    except Exception as e:
        print("Failed to calculate last opened for databases:", str(e))
        for db in dbs:
            db["last_opened"] = "Never"
            
    return render_template("databases.html", databases=dbs, db_stats=db_stats)



@app.route("/workspace")
@app.route("/workspace/<int:db_id>")
@login_required
def workspace(db_id=None):
    """Render SQL query workspace."""
    user_id = session["user_id"]
    if db_id:
        db_info = get_database_by_id(user_id, db_id)
        if db_info:
            session["active_db_id"] = db_id
            session["active_db_name"] = db_info["original_name"]
        else:
            flash("Database not found.", "error")
            return redirect(url_for("workspace"))
    else:
        # Resolve active DB path to set initial session variables if needed
        _get_db_path()

    return render_template("workspace.html")


@app.route("/history")
@login_required
def history_page():
    """Render Query history page."""
    user_id = session["user_id"]
    hist = get_history(user_id)
    return render_template("history.html", history=hist)


@app.route("/saved-queries")
@login_required
def saved_queries_page():
    """Render bookmarked queries page."""
    user_id = session["user_id"]
    saved = get_saved_queries(user_id)
    return render_template("saved_queries.html", saved_queries=saved)


@app.route("/profile")
@login_required
def profile_page():
    """Render User Profile options."""
    user_id = session["user_id"]
    stats = get_user_stats(user_id)
    return render_template("profile.html", stats=stats)


# ──────────────────────────────────────────────────────────────────────
# API Routes (JSON & Database Actions)
# ──────────────────────────────────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
@login_required
def upload_database():
    """Upload a SQLite database file to user directory."""
    user_id = session["user_id"]
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected"}), 400

    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({
            "success": False,
            "error": f"Invalid file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400

    user_db_dir = os.path.join(DATABASE_DIR, f"user_{user_id}")
    os.makedirs(user_db_dir, exist_ok=True)

    # Avoid duplicate file names by appending timestamp if it already exists
    base, extension = os.path.splitext(filename)
    clean_filename = filename
    counter = 1
    while os.path.exists(os.path.join(user_db_dir, clean_filename)):
        clean_filename = f"{base}_{counter}{extension}"
        counter += 1

    filepath = os.path.join(user_db_dir, clean_filename)
    file.save(filepath)

    # Validate it's a real SQLite database
    try:
        schema = get_schema(filepath)
        db_id = add_database(
            user_id=user_id,
            filename=clean_filename,
            original_name=filename,
            table_count=schema["table_count"],
            total_columns=schema["total_columns"],
            total_rows=schema["total_rows"],
            file_size=os.path.getsize(filepath)
        )
        session["active_db_id"] = db_id
        session["active_db_name"] = filename

        return jsonify({
            "success": True,
            "database": {
                "id": db_id,
                "name": filename,
                "file_size": os.path.getsize(filepath),
                "table_count": schema["table_count"],
                "total_columns": schema["total_columns"],
                "total_rows": schema["total_rows"]
            }
        })
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"success": False, "error": f"Invalid database file: {str(e)}"}), 400


@app.route("/api/database/delete/<int:db_id>", methods=["POST"])
@login_required
def delete_user_db(db_id):
    """Delete a user database from list."""
    user_id = session["user_id"]
    filename = delete_database(user_id, db_id)

    if filename:
        filepath = os.path.join(DATABASE_DIR, f"user_{user_id}", filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        # Clear session connection variables if this database was selected
        if session.get("active_db_id") == db_id:
            session.pop("active_db_id", None)
            session.pop("active_db_name", None)

        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Database not found"}), 404


@app.route("/api/database/select/<int:db_id>", methods=["POST"])
@login_required
def select_database(db_id):
    """Set database as active in session."""
    user_id = session["user_id"]
    db_info = get_database_by_id(user_id, db_id)
    if db_info:
        session["active_db_id"] = db_id
        session["active_db_name"] = db_info["original_name"]
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Database not found"}), 404


@app.route("/api/database/download/<int:db_id>")
@login_required
def download_user_db(db_id):
    """Download database file."""
    user_id = session["user_id"]
    db_info = get_database_by_id(user_id, db_id)
    if db_info:
        filepath = os.path.join(DATABASE_DIR, f"user_{user_id}", db_info["filename"])
        if os.path.exists(filepath):
            return send_file(
                filepath,
                as_attachment=True,
                download_name=db_info["original_name"]
            )
    flash("Database file not found.", "error")
    return redirect(url_for("databases_page"))


@app.route("/api/schema", methods=["GET"])
@login_required
def get_db_schema():
    """Get the active database schema."""
    db_path = _get_db_path()
    if not db_path:
        return jsonify({"success": False, "error": "No database selected"}), 404

    try:
        schema = get_schema(db_path)
        return jsonify({"success": True, "schema": schema})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/table-sample/<table_name>", methods=["GET"])
@login_required
def get_sample(table_name):
    """Get a sample of rows from a table."""
    db_path = _get_db_path()
    if not db_path:
        return jsonify({"success": False, "error": "No database selected"}), 404

    try:
        sample = get_table_sample(db_path, table_name)
        return jsonify({"success": True, "sample": sample})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/query", methods=["POST"])
@login_required
def process_query():
    """Process a natural language query and save to history."""
    db_path = _get_db_path()
    if not db_path:
        return jsonify({"success": False, "error": "No database selected"}), 404

    user_id = session["user_id"]
    active_db_id = session.get("active_db_id")

    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"success": False, "error": "No query provided"}), 400

    nl_query = data["query"].strip()
    if not nl_query:
        return jsonify({"success": False, "error": "Empty query"}), 400

    try:
        schema = get_schema(db_path)
        result = generate_query(nl_query, schema)

        if not result["valid"] or not result["sql"]:
            return jsonify({
                "success": False,
                "error": result.get("explanation", "Could not generate SQL"),
                "confidence": result.get("confidence", 0),
                "warnings": result.get("warnings", [])
            })

        # Validate SQL
        is_valid, validation_msg = validate_query(result["sql"])
        if not is_valid:
            return jsonify({
                "success": False,
                "error": validation_msg,
                "sql": result["sql"],
                "confidence": result["confidence"]
            })

        # Execute
        exec_result = execute_query(db_path, result["sql"])

        if exec_result["success"]:
            # Add to persistent query history
            add_history(
                user_id=user_id,
                database_id=active_db_id,
                nl_query=nl_query,
                generated_sql=result["sql"],
                confidence=result["confidence"],
                row_count=exec_result.get("row_count", 0),
                execution_time=exec_result.get("execution_time", 0)
            )

        return jsonify({
            "success": exec_result["success"],
            "sql": result["sql"],
            "explanation": result["explanation"],
            "confidence": result["confidence"],
            "warnings": result.get("warnings", []),
            "tables_used": result.get("tables_used", []),
            "validation": "safe",
            "columns": exec_result.get("columns", []),
            "rows": exec_result.get("rows", []),
            "execution_time": exec_result.get("execution_time", 0),
            "row_count": exec_result.get("row_count", 0),
            "error": exec_result.get("error")
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/execute-sql", methods=["POST"])
@login_required
def execute_raw_sql():
    """Execute a raw SQL query (for manual editing)."""
    db_path = _get_db_path()
    if not db_path:
        return jsonify({"success": False, "error": "No database selected"}), 404

    data = request.get_json()
    if not data or "sql" not in data:
        return jsonify({"success": False, "error": "No SQL provided"}), 400

    sql = data["sql"].strip()
    if not sql:
        return jsonify({"success": False, "error": "Empty SQL"}), 400

    is_valid, validation_msg = validate_query(sql)
    if not is_valid:
        return jsonify({"success": False, "error": validation_msg})

    result = execute_query(db_path, sql)
    return jsonify({
        "success": result["success"],
        "columns": result.get("columns", []),
        "rows": result.get("rows", []),
        "execution_time": result.get("execution_time", 0),
        "row_count": result.get("row_count", 0),
        "error": result.get("error")
    })


@app.route("/api/query/save", methods=["POST"])
@login_required
def save_query():
    """Bookmark a query."""
    user_id = session["user_id"]
    active_db_id = session.get("active_db_id")
    if not active_db_id:
        return jsonify({"success": False, "error": "No active database selected"}), 400

    data = request.get_json()
    if not data or "name" not in data or "nl_query" not in data or "sql" not in data:
        return jsonify({"success": False, "error": "Incomplete query data provided"}), 400

    try:
        add_saved_query(
            user_id=user_id,
            database_id=active_db_id,
            name=data["name"],
            nl_query=data["nl_query"],
            generated_sql=data["sql"]
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/saved/delete/<int:saved_id>", methods=["POST"])
@login_required
def delete_saved(saved_id):
    """Delete a saved query."""
    user_id = session["user_id"]
    delete_saved_query(user_id, saved_id)
    return jsonify({"success": True})


@app.route("/api/history/delete/<int:history_id>", methods=["POST"])
@login_required
def delete_history_log(history_id):
    """Delete a query history log entry."""
    user_id = session["user_id"]
    delete_history_item(user_id, history_id)
    return jsonify({"success": True})


@app.route("/api/suggestions", methods=["GET"])
@login_required
def get_suggestions_list():
    """Generate suggested questions based on active schema."""
    db_path = _get_db_path()
    if not db_path:
        return jsonify({"success": False, "error": "No database selected"}), 404

    try:
        schema = get_schema(db_path)
        suggestions = generate_suggestions(schema)
        return jsonify({"success": True, "suggestions": suggestions})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/insights", methods=["GET"])
@login_required
def get_insights():
    """Get database insights and statistics."""
    db_path = _get_db_path()
    if not db_path:
        return jsonify({"success": False, "error": "No database selected"}), 404

    try:
        insights = get_database_insights(db_path)
        return jsonify({"success": True, "insights": insights})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/export/csv", methods=["POST"])
@login_required
def export_csv():
    """Export query results as CSV."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    columns = data.get("columns", [])
    rows = data.get("rows", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows(rows)

    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)

    return send_file(
        mem,
        mimetype="text/csv",
        as_attachment=True,
        download_name="askdb_export.csv"
    )


@app.route("/api/export/excel", methods=["POST"])
@login_required
def export_excel():
    """Export query results as Excel."""
    try:
        from openpyxl import Workbook
    except ImportError:
        return jsonify({"success": False, "error": "openpyxl not installed"}), 500

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    columns = data.get("columns", [])
    rows = data.get("rows", [])

    wb = Workbook()
    ws = wb.active
    ws.title = "AskDB Export"
    ws.append(columns)
    for row in rows:
        ws.append(row)

    mem = io.BytesIO()
    wb.save(mem)
    mem.seek(0)

    return send_file(
        mem,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="askdb_export.xlsx"
    )


@app.route("/api/status", methods=["GET"])
@login_required
def get_status():
    """Check if database is connected."""
    db_path = _get_db_path()
    if db_path:
        try:
            schema = get_schema(db_path)
            return jsonify({
                "success": True,
                "connected": True,
                "database": schema["database_name"],
                "table_count": schema["table_count"]
            })
        except Exception:
            pass
    return jsonify({"success": True, "connected": False})


# ──────────────────────────────────────────────────────────────────────
# Profile Post Handlers
# ──────────────────────────────────────────────────────────────────────

@app.route("/profile/change-password", methods=["POST"])
@login_required
def profile_change_password():
    """Change user password."""
    user_id = session["user_id"]
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_new = request.form.get("confirm_new", "")

    if not current_password or not new_password or not confirm_new:
        flash("All fields are required.", "error")
        return redirect(url_for("profile_page"))

    if new_password != confirm_new:
        flash("New passwords do not match.", "error")
        return redirect(url_for("profile_page"))

    if len(new_password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("profile_page"))

    user = get_user_by_id(user_id)
    if user and check_password_hash(user["password_hash"], current_password):
        hashed = generate_password_hash(new_password)
        update_password(user_id, hashed)
        flash("Password updated successfully!", "success")
    else:
        flash("Incorrect current password.", "error")

    return redirect(url_for("profile_page"))


@app.route("/profile/reset-history", methods=["POST"])
@login_required
def profile_reset_history():
    """Clear query history."""
    user_id = session["user_id"]
    clear_history(user_id)
    flash("Query history cleared.", "success")
    return redirect(url_for("profile_page"))


@app.route("/profile/reset-databases", methods=["POST"])
@login_required
def profile_reset_databases():
    """Delete all user uploaded databases."""
    user_id = session["user_id"]
    dbs = get_user_databases(user_id)
    for db in dbs:
        delete_user_db(db["id"])
    flash("All databases deleted.", "success")
    return redirect(url_for("profile_page"))


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
