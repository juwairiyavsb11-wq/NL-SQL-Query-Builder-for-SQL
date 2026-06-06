"""
AskDB — Schema Reader
Reads SQLite database schema: tables, columns, types, relationships, row counts.
"""

import sqlite3
import os


def get_schema(db_path):
    """
    Extract complete schema information from a SQLite database.
    Returns a dict with tables, columns, types, primary keys, foreign keys, and row counts.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    schema = {
        "database_name": os.path.basename(db_path),
        "file_size": os.path.getsize(db_path),
        "tables": []
    }

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    table_names = [row["name"] for row in cursor.fetchall()]

    for table_name in table_names:
        table_info = {
            "name": table_name,
            "columns": [],
            "primary_keys": [],
            "foreign_keys": [],
            "row_count": 0
        }

        # Get columns
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = cursor.fetchall()
        for col in columns:
            col_info = {
                "name": col["name"],
                "type": col["type"] if col["type"] else "TEXT",
                "notnull": bool(col["notnull"]),
                "default": col["dflt_value"],
                "primary_key": bool(col["pk"])
            }
            table_info["columns"].append(col_info)
            if col["pk"]:
                table_info["primary_keys"].append(col["name"])

        # Get foreign keys
        cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')
        fks = cursor.fetchall()
        for fk in fks:
            fk_info = {
                "from_column": fk["from"],
                "to_table": fk["table"],
                "to_column": fk["to"]
            }
            table_info["foreign_keys"].append(fk_info)

        # Get row count
        try:
            cursor.execute(f'SELECT COUNT(*) as cnt FROM "{table_name}"')
            table_info["row_count"] = cursor.fetchone()["cnt"]
        except Exception:
            table_info["row_count"] = 0

        schema["tables"].append(table_info)

    # Compute totals
    schema["table_count"] = len(schema["tables"])
    schema["total_columns"] = sum(len(t["columns"]) for t in schema["tables"])
    schema["total_rows"] = sum(t["row_count"] for t in schema["tables"])

    # Build relationships map
    schema["relationships"] = []
    for table in schema["tables"]:
        for fk in table["foreign_keys"]:
            schema["relationships"].append({
                "from_table": table["name"],
                "from_column": fk["from_column"],
                "to_table": fk["to_table"],
                "to_column": fk["to_column"]
            })

    conn.close()
    return schema


def get_table_sample(db_path, table_name, limit=5):
    """
    Get a sample of rows from a table.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(f'SELECT * FROM "{table_name}" LIMIT {int(limit)}')
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        data = [dict(row) for row in rows]
        return {"columns": columns, "data": data}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


def get_database_insights(db_path):
    """
    Get high-level database insights/statistics.
    """
    schema = get_schema(db_path)

    insights = {
        "total_tables": schema["table_count"],
        "total_columns": schema["total_columns"],
        "total_rows": schema["total_rows"],
        "tables": []
    }

    for table in schema["tables"]:
        insights["tables"].append({
            "name": table["name"],
            "row_count": table["row_count"],
            "column_count": len(table["columns"])
        })

    # Sort by row count descending
    insights["tables"].sort(key=lambda t: t["row_count"], reverse=True)
    insights["largest_table"] = insights["tables"][0]["name"] if insights["tables"] else None

    return insights
