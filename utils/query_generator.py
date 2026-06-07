"""
AskDB — Query Generator
Converts natural language questions into SQL queries using rule-based pattern matching,
keyword extraction, and schema-aware mapping.
"""

import re
import random


# ──────────────────────────────────────────────────────────────────────
# Keyword / intent dictionaries
# ──────────────────────────────────────────────────────────────────────

AGGREGATION_KEYWORDS = {
    "total": "SUM", "sum": "SUM", "sum of": "SUM",
    "average": "AVG", "avg": "AVG", "mean": "AVG",
    "count": "COUNT", "how many": "COUNT", "number of": "COUNT",
    "maximum": "MAX", "max": "MAX",
    "minimum": "MIN", "min": "MIN",
}

SORT_KEYWORDS = {
    "top": "DESC", "highest": "DESC", "most": "DESC", "largest": "DESC",
    "best": "DESC", "greatest": "DESC", "expensive": "DESC",
    "bottom": "ASC", "lowest": "ASC", "least": "ASC", "smallest": "ASC",
    "cheapest": "ASC", "worst": "ASC", "fewest": "ASC",
    "ascending": "ASC", "descending": "DESC",
    "alphabetical": "ASC", "alphabetically": "ASC",
    "newest": "DESC", "oldest": "ASC", "latest": "DESC", "earliest": "ASC",
    "recent": "DESC",
}

COMPARISON_PATTERNS = [
    (r"more than\s+(\d+(?:\.\d+)?)", ">"),
    (r"greater than\s+(\d+(?:\.\d+)?)", ">"),
    (r"above\s+(\d+(?:\.\d+)?)", ">"),
    (r"over\s+(\d+(?:\.\d+)?)", ">"),
    (r"exceeds?\s+(\d+(?:\.\d+)?)", ">"),
    (r"at least\s+(\d+(?:\.\d+)?)", ">="),
    (r"less than\s+(\d+(?:\.\d+)?)", "<"),
    (r"below\s+(\d+(?:\.\d+)?)", "<"),
    (r"under\s+(\d+(?:\.\d+)?)", "<"),
    (r"fewer than\s+(\d+(?:\.\d+)?)", "<"),
    (r"at most\s+(\d+(?:\.\d+)?)", "<="),
    (r"no more than\s+(\d+(?:\.\d+)?)", "<="),
    (r"equal to\s+(\d+(?:\.\d+)?)", "="),
    (r"exactly\s+(\d+(?:\.\d+)?)", "="),
    (r"between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)", "BETWEEN"),
]

TIME_KEYWORDS = {
    "today": "date('now')",
    "yesterday": "date('now', '-1 day')",
    "this week": "date('now', '-7 days')",
    "last week": "date('now', '-14 days')",
    "this month": "date('now', 'start of month')",
    "last month": "date('now', 'start of month', '-1 month')",
    "this year": "date('now', 'start of year')",
    "last year": "date('now', 'start of year', '-1 year')",
    "past week": "date('now', '-7 days')",
    "past month": "date('now', '-30 days')",
    "past year": "date('now', '-365 days')",
    "last 7 days": "date('now', '-7 days')",
    "last 30 days": "date('now', '-30 days')",
    "last 90 days": "date('now', '-90 days')",
}

LIMIT_PATTERNS = [
    (r"top\s+(\d+)", None),
    (r"first\s+(\d+)", None),
    (r"(\d+)\s+(?:results?|rows?|records?|entries|items)", None),
    (r"limit\s+(\d+)", None),
    (r"show\s+(\d+)", None),
]

STOP_WORDS = {
    "show", "me", "get", "find", "list", "display", "give", "fetch",
    "retrieve", "return", "what", "which", "who", "where", "how",
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "and", "or", "but", "not", "all", "each", "every", "any",
    "that", "this", "these", "those", "it", "its", "them", "their",
    "do", "does", "did", "have", "has", "had", "can", "could",
    "will", "would", "shall", "should", "may", "might", "must",
    "i", "my", "our", "we", "you", "your", "please", "also",
    "than", "then", "so", "if", "when", "as", "about",
    "database", "table", "column", "data", "query", "select",
}


# ──────────────────────────────────────────────────────────────────────
# Fuzzy matching helpers
# ──────────────────────────────────────────────────────────────────────

def _normalize(text):
    """Lowercase, strip, and collapse whitespace."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokenize(text):
    """Split into alphanumeric tokens."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _similarity(a, b):
    """Simple similarity metric (shared characters ratio)."""
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.85
    # Trigram similarity
    def trigrams(s):
        return set(s[i:i+3] for i in range(max(len(s)-2, 1)))
    ta, tb = trigrams(a), trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta | tb), 1)


def _find_best_table(token, schema):
    """Find the best matching table for a token."""
    best_score = 0
    best_table = None
    for table in schema["tables"]:
        tname = table["name"].lower()
        # Exact or plural match
        if token == tname or token + "s" == tname or token == tname + "s" or token + "es" == tname:
            return table["name"]
        
        # Skip similarity checks for short tokens
        if len(token) < 2:
            continue

        score = _similarity(token, tname)
        if score > best_score:
            best_score = score
            best_table = table["name"]
    return best_table if best_score >= 0.5 else None


def _find_best_column(token, table_obj):
    """Find the best matching column for a token in a table."""
    best_score = 0
    best_col = None
    for col in table_obj["columns"]:
        cname = col["name"].lower()
        clean_cname = cname.replace("_", "")
        clean_token = token.replace("_", "")
        if clean_token == clean_cname or token == cname:
            return col["name"]

        # Skip similarity checks for short tokens
        if len(clean_token) < 2:
            continue

        score = _similarity(clean_token, clean_cname)
        if score > best_score:
            best_score = score
            best_col = col["name"]
    return best_col if best_score >= 0.45 else None


def _find_column_across_tables(token, schema):
    """Search for a column across all tables."""
    for table in schema["tables"]:
        col = _find_best_column(token, table)
        if col:
            return table["name"], col
    return None, None


def _get_table_obj(table_name, schema):
    """Get the table object from schema by name."""
    for t in schema["tables"]:
        if t["name"].lower() == table_name.lower():
            return t
    return None


def _find_date_columns(table_obj):
    """Find columns that look like dates."""
    date_hints = ["date", "time", "created", "updated", "timestamp", "ordered", "joined", "registered"]
    results = []
    for col in table_obj["columns"]:
        cname = col["name"].lower()
        ctype = col["type"].lower()
        if any(h in cname for h in date_hints) or "date" in ctype or "time" in ctype:
            results.append(col["name"])
    return results


def _find_numeric_columns(table_obj):
    """Find numeric columns."""
    numeric_types = ["int", "integer", "real", "float", "double", "numeric", "decimal", "number"]
    results = []
    for col in table_obj["columns"]:
        ctype = col["type"].lower()
        cname = col["name"].lower()
        if any(nt in ctype for nt in numeric_types):
            results.append(col["name"])
        elif any(hint in cname for hint in ["amount", "price", "total", "cost", "quantity", "count", "score", "rating", "salary", "revenue", "age", "stock"]):
            results.append(col["name"])
    return results


def _find_name_column(table_obj):
    """Find a column that represents a name/label."""
    name_hints = ["name", "title", "label", "description", "email", "username"]
    for col in table_obj["columns"]:
        cname = col["name"].lower()
        if any(h in cname for h in name_hints):
            return col["name"]
    # Fall back to second column (first is usually ID)
    if len(table_obj["columns"]) > 1:
        return table_obj["columns"][1]["name"]
    return table_obj["columns"][0]["name"] if table_obj["columns"] else None


def _get_join_path(from_table, to_table, schema):
    """Find a join path between two tables using foreign keys."""
    for rel in schema.get("relationships", []):
        if rel["from_table"].lower() == from_table.lower() and rel["to_table"].lower() == to_table.lower():
            return rel
        if rel["from_table"].lower() == to_table.lower() and rel["to_table"].lower() == from_table.lower():
            return {
                "from_table": rel["to_table"],
                "from_column": rel["to_column"],
                "to_table": rel["from_table"],
                "to_column": rel["from_column"]
            }
    return None


# ──────────────────────────────────────────────────────────────────────
# Main generation logic
# ──────────────────────────────────────────────────────────────────────

def generate_query(nl_query, schema):
    """
    Convert a natural language query to SQL.
    Returns a dict with sql, explanation, confidence, and validation info.
    """
    original = nl_query.strip()
    query = _normalize(nl_query)
    tokens = _tokenize(query)

    confidence = 60  # Start at 60% base
    explanations = []
    warnings = []

    # ── Step 1: Identify target tables ──
    matched_tables = []
    for token in tokens:
        if token in STOP_WORDS:
            continue
        table = _find_best_table(token, schema)
        if table and table not in matched_tables:
            matched_tables.append(table)

    # If no table matched, try multi-word combinations
    if not matched_tables:
        for i in range(len(tokens) - 1):
            combined = tokens[i] + "_" + tokens[i+1]
            table = _find_best_table(combined, schema)
            if table and table not in matched_tables:
                matched_tables.append(table)

    # Default to the table with the most rows if nothing found
    if not matched_tables and schema["tables"]:
        default_table = max(schema["tables"], key=lambda t: t["row_count"])
        matched_tables.append(default_table["name"])
        confidence -= 15
        warnings.append("Could not identify a specific table; using the largest table.")

    primary_table = matched_tables[0] if matched_tables else None
    if not primary_table:
        return {
            "sql": None,
            "explanation": "Could not understand the query. Please try rephrasing.",
            "confidence": 0,
            "valid": False,
            "warnings": ["No tables found in the database."]
        }

    primary_table_obj = _get_table_obj(primary_table, schema)
    confidence += 10

    # ── Step 2: Detect if this is a "top N" ranking query ──
    is_top_n = bool(re.search(r"top\s+\d+", query))

    # ── Step 2b: Detect aggregation intent ──
    agg_func = None
    agg_column = None
    if not is_top_n:  # "top N" queries are rankings, not aggregations
        for keyword, func in AGGREGATION_KEYWORDS.items():
            if keyword in query:
                agg_func = func
                # Try to find what to aggregate
                idx = query.index(keyword)
                after = query[idx + len(keyword):].strip()
                after_tokens = _tokenize(after)
                for at in after_tokens[:3]:
                    if at in STOP_WORDS:
                        continue
                    col = _find_best_column(at, primary_table_obj)
                    if col:
                        agg_column = col
                        break
                if not agg_column and agg_func != "COUNT":
                    # Try numeric columns
                    num_cols = _find_numeric_columns(primary_table_obj)
                    if num_cols:
                        agg_column = num_cols[0]
                confidence += 8
                break

    # ── Step 3: Detect GROUP BY intent ──
    group_by_col = None
    # Skip GROUP BY for "top N" queries — "by X" means ORDER BY, not GROUP BY
    if not is_top_n:
        group_patterns = [
            r"(?:by|per|for each|group by|grouped by|for every)\s+(\w+)",
            r"(\w+)\s+wise",
        ]
        for pattern in group_patterns:
            m = re.search(pattern, query)
            if m:
                token = m.group(1)
                col = _find_best_column(token, primary_table_obj)
                if col:
                    group_by_col = col
                    confidence += 8
                    break
                # Maybe it's a column in another table
                tbl, col = _find_column_across_tables(token, schema)
                if col and tbl:
                    if tbl not in matched_tables:
                        matched_tables.append(tbl)
                    group_by_col = f"{tbl}.{col}"
                    confidence += 5
                    break

    # ── Step 4: Detect ORDER BY / LIMIT ──
    order_dir = None
    order_col = None
    limit_n = None

    for keyword, direction in SORT_KEYWORDS.items():
        if keyword in query:
            order_dir = direction
            # Find what to order by
            idx = query.index(keyword)
            surrounding = query[max(0, idx-20):idx+len(keyword)+30]
            surr_tokens = _tokenize(surrounding)
            for st in surr_tokens:
                if st in STOP_WORDS or st == keyword:
                    continue
                col = _find_best_column(st, primary_table_obj)
                if col:
                    order_col = col
                    break
            break

    if not order_col and order_dir:
        # Default to a numeric column
        num_cols = _find_numeric_columns(primary_table_obj)
        if num_cols:
            order_col = num_cols[0]

    for pattern, _ in LIMIT_PATTERNS:
        m = re.search(pattern, query)
        if m:
            limit_n = int(m.group(1))
            confidence += 5
            break

    # If "top N" was detected, ensure DESC order and SELECT *
    if is_top_n:
        order_dir = order_dir or "DESC"
        if not order_col:
            # Try to find the column mentioned after "by" in the query
            by_match = re.search(r"by\s+(\w+)", query)
            if by_match:
                col = _find_best_column(by_match.group(1), primary_table_obj)
                if col:
                    order_col = col
            if not order_col:
                num_cols = _find_numeric_columns(primary_table_obj)
                if num_cols:
                    order_col = num_cols[0]
        confidence += 10

    # ── Step 5: Detect WHERE conditions ──
    where_clauses = []

    # Comparison patterns
    for pattern, op in COMPARISON_PATTERNS:
        m = re.search(pattern, query)
        if m:
            if op == "BETWEEN":
                val1, val2 = m.group(1), m.group(2)
                # Find what column
                before = query[:m.start()]
                before_tokens = _tokenize(before)
                comp_col = None
                for bt in reversed(before_tokens):
                    if bt in STOP_WORDS:
                        continue
                    col = _find_best_column(bt, primary_table_obj)
                    if col:
                        comp_col = col
                        break
                if comp_col:
                    where_clauses.append(f'"{comp_col}" BETWEEN {val1} AND {val2}')
                    confidence += 8
            else:
                val = m.group(1)
                before = query[:m.start()]
                before_tokens = _tokenize(before)
                comp_col = None
                for bt in reversed(before_tokens):
                    if bt in STOP_WORDS:
                        continue
                    col = _find_best_column(bt, primary_table_obj)
                    if col:
                        comp_col = col
                        break
                if not comp_col:
                    # Check context: might be about COUNT in HAVING
                    if agg_func == "COUNT" and group_by_col:
                        where_clauses.append(f"__HAVING__ COUNT(*) {op} {val}")
                        confidence += 8
                    else:
                        num_cols = _find_numeric_columns(primary_table_obj)
                        if num_cols:
                            comp_col = num_cols[0]
                if comp_col:
                    where_clauses.append(f'"{comp_col}" {op} {val}')
                    confidence += 8
            break

    # Wildcard / LIKE patterns (e.g. starts with, ends with, contains)
    LIKE_PATTERNS = [
        (r"(?:starts with|starting with|start with)\s+(?:letter\s+)?['\"]?([a-zA-Z0-9_\-\s]+)['\"]?", "LIKE", "{val}%"),
        (r"(?:ends with|ending with|end with)\s+(?:letter\s+)?['\"]?([a-zA-Z0-9_\-\s]+)['\"]?", "LIKE", "%{val}"),
        (r"(?:contains|containing)\s+['\"]?([a-zA-Z0-9_\-\s]+)['\"]?", "LIKE", "%{val}%"),
    ]

    for pattern, op, format_str in LIKE_PATTERNS:
        m = re.search(pattern, query)
        if m:
            val = m.group(1).strip()
            # Find the column before the wildcard phrase
            before = query[:m.start()]
            before_tokens = _tokenize(before)
            comp_col = None
            for bt in reversed(before_tokens):
                if bt in STOP_WORDS:
                    continue
                col = _find_best_column(bt, primary_table_obj)
                if col:
                    comp_col = col
                    break
            
            if not comp_col:
                comp_col = _find_name_column(primary_table_obj)
                
            if comp_col:
                sql_val = format_str.format(val=val)
                where_clauses.append(f'"{comp_col}" LIKE \'{sql_val}\'')
                confidence += 10
            break

    # Time-based conditions
    for time_phrase, sql_func in TIME_KEYWORDS.items():
        if time_phrase in query:
            date_cols = _find_date_columns(primary_table_obj)
            if date_cols:
                date_col = date_cols[0]
                if "last" in time_phrase and "month" in time_phrase:
                    where_clauses.append(
                        f'"{date_col}" >= {sql_func} AND "{date_col}" < date(\'now\', \'start of month\')'
                    )
                elif "this" in time_phrase:
                    where_clauses.append(f'"{date_col}" >= {sql_func}')
                else:
                    where_clauses.append(f'"{date_col}" >= {sql_func}')
                confidence += 10
            else:
                warnings.append(f"No date column found for time filter '{time_phrase}'.")
            break

    # String value matching (e.g., "from New York", "status is active")
    # Look for quoted strings or capitalized words that could be values
    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', original)
    for q in quoted:
        val = q[0] or q[1]
        # Try to figure out which column this value belongs to
        for col in primary_table_obj["columns"]:
            ctype = col["type"].lower()
            if "text" in ctype or "char" in ctype or "varchar" in ctype or ctype == "":
                where_clauses.append(f'"{col["name"]}" = \'{val}\'')
                confidence += 5
                break

    # Look for "status is/= active" type patterns
    status_pattern = r"(?:status|state|type|category)\s+(?:is|=|equals?)\s+['\"]?(\w+)['\"]?"
    m = re.search(status_pattern, query)
    if m:
        status_val = m.group(1)
        status_col = _find_best_column("status", primary_table_obj)
        if not status_col:
            status_col = _find_best_column("state", primary_table_obj)
        if not status_col:
            status_col = _find_best_column("type", primary_table_obj)
        if status_col:
            where_clauses.append(f'"{status_col}" = \'{status_val}\'')
            confidence += 8

    # Look for "from <city/place>" patterns
    from_pattern = r"(?:from|in|at|located in)\s+([A-Z][a-zA-Z\s]+?)(?:\s+who|\s+that|\s+with|$|\.|\,)"
    m = re.search(from_pattern, original)
    if m:
        place = m.group(1).strip()
        # Find a text column that could be a location
        loc_hints = ["city", "location", "address", "state", "country", "region", "place"]
        loc_col = None
        for hint in loc_hints:
            col = _find_best_column(hint, primary_table_obj)
            if col:
                loc_col = col
                break
        if loc_col:
            where_clauses.append(f'"{loc_col}" = \'{place}\'')
            confidence += 8

    # ── Step 6: Detect JOINs needed ──
    join_clauses = []
    if len(matched_tables) > 1:
        for i in range(1, len(matched_tables)):
            join_path = _get_join_path(primary_table, matched_tables[i], schema)
            if join_path:
                join_clauses.append(
                    f'JOIN "{matched_tables[i]}" ON "{join_path["from_table"]}"."{join_path["from_column"]}" = "{join_path["to_table"]}"."{join_path["to_column"]}"'
                )
                confidence += 5
            else:
                # Try reverse or intermediate joins
                for other_table in matched_tables:
                    if other_table != matched_tables[i]:
                        jp = _get_join_path(other_table, matched_tables[i], schema)
                        if jp:
                            join_clauses.append(
                                f'JOIN "{matched_tables[i]}" ON "{jp["from_table"]}"."{jp["from_column"]}" = "{jp["to_table"]}"."{jp["to_column"]}"'
                            )
                            confidence += 3
                            break

    # ── Step 7: Build SELECT clause ──
    select_parts = []

    if agg_func and group_by_col:
        clean_group = group_by_col.split(".")[-1] if "." in group_by_col else group_by_col
        select_parts.append(f'"{clean_group}"')
        if agg_func == "COUNT":
            select_parts.append("COUNT(*) as count")
        elif agg_column:
            select_parts.append(f'{agg_func}("{agg_column}") as {agg_func.lower()}_{agg_column}')
        else:
            select_parts.append("COUNT(*) as count")
    elif agg_func and not group_by_col:
        if agg_func == "COUNT":
            select_parts.append("COUNT(*) as total_count")
        elif agg_column:
            select_parts.append(f'{agg_func}("{agg_column}") as {agg_func.lower()}_{agg_column}')
        else:
            select_parts.append("COUNT(*) as total_count")
    else:
        # For "top N" queries, always show all columns
        if is_top_n:
            select_parts = ["*"]
        else:
            # Check if specific columns were mentioned
            mentioned_cols = []
            for token in tokens:
                if token in STOP_WORDS:
                    continue
                col = _find_best_column(token, primary_table_obj)
                if col and col not in mentioned_cols:
                    # Avoid adding table names as columns
                    if token != primary_table.lower() and token + "s" != primary_table.lower():
                        mentioned_cols.append(col)
            if mentioned_cols and len(mentioned_cols) <= 5:
                select_parts = [f'"{c}"' for c in mentioned_cols]
            else:
                select_parts = ["*"]

    select_clause = ", ".join(select_parts) if select_parts else "*"

    # ── Step 8: Assemble SQL ──
    # Separate HAVING clauses from WHERE clauses
    having_clauses = [c.replace("__HAVING__ ", "") for c in where_clauses if c.startswith("__HAVING__")]
    where_clauses = [c for c in where_clauses if not c.startswith("__HAVING__")]

    sql_parts = [f'SELECT {select_clause}']
    sql_parts.append(f'FROM "{primary_table}"')

    if join_clauses:
        sql_parts.extend(join_clauses)

    if where_clauses:
        sql_parts.append("WHERE " + " AND ".join(where_clauses))

    if group_by_col:
        clean_group = group_by_col.split(".")[-1] if "." in group_by_col else group_by_col
        sql_parts.append(f'GROUP BY "{clean_group}"')

    if having_clauses:
        sql_parts.append("HAVING " + " AND ".join(having_clauses))

    if order_col:
        sql_parts.append(f'ORDER BY "{order_col}" {order_dir or "DESC"}')

    if limit_n:
        sql_parts.append(f"LIMIT {limit_n}")
    elif not group_by_col and not agg_func:
        # Default limit for safety
        sql_parts.append("LIMIT 100")

    sql = "\n".join(sql_parts)

    # ── Step 9: Generate explanation ──
    explanation = _generate_explanation(
        primary_table, matched_tables, agg_func, agg_column,
        group_by_col, order_col, order_dir, limit_n,
        where_clauses, having_clauses, join_clauses
    )

    # Clamp confidence
    confidence = min(max(confidence, 15), 98)

    return {
        "sql": sql,
        "explanation": explanation,
        "confidence": confidence,
        "valid": True,
        "warnings": warnings,
        "tables_used": matched_tables
    }


def _generate_explanation(primary_table, tables, agg_func, agg_col,
                          group_col, order_col, order_dir, limit_n,
                          where_clauses, having_clauses, join_clauses):
    """Generate a human-friendly explanation of the query."""
    parts = []

    if agg_func and agg_col:
        func_names = {"SUM": "total", "AVG": "average", "MAX": "maximum", "MIN": "minimum", "COUNT": "count"}
        parts.append(f"This query calculates the {func_names.get(agg_func, agg_func.lower())} of {agg_col}")
    elif agg_func == "COUNT":
        parts.append(f"This query counts records")
    else:
        parts.append(f"This query retrieves data")

    parts.append(f"from the {primary_table} table")

    if join_clauses:
        other_tables = [t for t in tables if t != primary_table]
        if other_tables:
            parts.append(f"joined with {', '.join(other_tables)}")

    if where_clauses:
        conditions = []
        for wc in where_clauses:
            # Clean up for readability
            clean = wc.replace('"', '').replace("'", "'")
            conditions.append(clean)
        parts.append(f"where {' and '.join(conditions)}")

    if group_col:
        clean_group = group_col.split(".")[-1] if "." in group_col else group_col
        parts.append(f"grouped by {clean_group}")

    if having_clauses:
        parts.append(f"having {' and '.join(having_clauses)}")

    if order_col:
        direction = "descending" if order_dir == "DESC" else "ascending"
        parts.append(f"sorted by {order_col} in {direction} order")

    if limit_n:
        parts.append(f"limited to {limit_n} results")

    return " ".join(parts) + "."


def generate_suggestions(schema):
    """
    Generate contextual suggested questions based on the database schema.
    """
    suggestions = []

    for table in schema["tables"]:
        tname = table["name"]
        name_col = _find_name_column(table)
        num_cols = _find_numeric_columns(table)
        date_cols = _find_date_columns(table)

        # Basic show all
        suggestions.append({
            "text": f"Show all {tname}",
            "category": "explore"
        })

        # Count
        suggestions.append({
            "text": f"How many {tname} are there?",
            "category": "count"
        })

        # Top N by numeric column
        if num_cols:
            col = num_cols[0]
            suggestions.append({
                "text": f"Top 10 {tname} by {col}",
                "category": "ranking"
            })
            suggestions.append({
                "text": f"Average {col} of {tname}",
                "category": "aggregation"
            })

        # Recent entries
        if date_cols:
            dcol = date_cols[0]
            suggestions.append({
                "text": f"Show {tname} from this month",
                "category": "time"
            })
            suggestions.append({
                "text": f"Show latest {tname}",
                "category": "time"
            })

        # Group by for tables with categorical-looking columns
        for col in table["columns"]:
            cname = col["name"].lower()
            if any(h in cname for h in ["status", "category", "type", "state", "city", "country", "region"]):
                suggestions.append({
                    "text": f"Count {tname} by {col['name']}",
                    "category": "grouping"
                })
                break

    # Cross-table suggestions if relationships exist
    for rel in schema.get("relationships", []):
        suggestions.append({
            "text": f"Show {rel['from_table']} with their {rel['to_table']}",
            "category": "join"
        })

    # Shuffle and limit
    random.shuffle(suggestions)
    return suggestions[:8]
