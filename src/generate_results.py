#!/usr/bin/env python3
"""Generate results.md by running all SQL demo scripts and capturing output."""

import os, re, textwrap
import oracledb
from dotenv import load_dotenv

load_dotenv()

# --- SQL splitter (same logic as run_demos.py) ---

def split_sql(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    stmts = []
    buf = []
    brace_depth = 0
    for line in text.split('\n'):
        stripped = line.strip()
        if not buf and (not stripped or stripped.startswith('--')):
            continue
        brace_depth += line.count('{') - line.count('}')
        buf.append(line)
        if stripped.endswith(';') and brace_depth <= 0:
            stmt = '\n'.join(buf).strip().rstrip(';').strip()
            if stmt and not all(l.strip().startswith('--') or not l.strip() for l in stmt.split('\n')):
                stmts.append(stmt)
            buf = []
            brace_depth = 0
        elif stripped == '/':
            stmt = '\n'.join(buf[:-1]).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            brace_depth = 0
    if buf:
        stmt = '\n'.join(buf).strip().rstrip(';').strip()
        if stmt and not all(l.strip().startswith('--') or not l.strip() for l in stmt.split('\n')):
            stmts.append(stmt)
    return stmts


def clean_sql(stmt):
    """Return SQL with leading comment lines stripped."""
    lines = stmt.split('\n')
    result = []
    past_comments = False
    for l in lines:
        if not past_comments and l.strip().startswith('--'):
            continue
        past_comments = True
        result.append(l)
    return '\n'.join(result).strip()


def format_table(cols, rows, max_rows=15):
    """Format rows as a markdown-style table, capped at max_rows."""
    # Compute widths
    widths = []
    for j, c in enumerate(cols):
        w = len(str(c))
        for r in rows[:max_rows]:
            val = str(r[j]) if r[j] is not None else ''
            # Truncate wide values
            if len(val) > 40:
                val = val[:37] + '...'
            w = max(w, len(val))
        widths.append(min(w, 40))

    def fmt_row(vals):
        parts = []
        for j, v in enumerate(vals):
            s = str(v) if v is not None else ''
            if len(s) > 40:
                s = s[:37] + '...'
            parts.append(s.ljust(widths[j]))
        return ' | '.join(parts)

    lines = []
    lines.append(fmt_row(cols))
    lines.append('-+-'.join('-' * widths[j] for j in range(len(cols))))
    shown = rows[:max_rows]
    for r in shown:
        lines.append(fmt_row(r))
    if len(rows) > max_rows:
        lines.append(f'... ({len(rows) - max_rows} more rows)')
    lines.append(f'({len(rows)} row{"s" if len(rows) != 1 else ""} total)')
    return '\n'.join(lines)


# --- Metadata: intent per script and per query ---

SCRIPT_META = {
    '00_setup.sql': {
        'title': 'Foundation: Tables & Data Extraction',
        'intro': 'Loads all CSV files via an External Table, then derives `runs` (one row per activity) and `samples` (one row per GPS point) from the raw data.',
        'query_intents': {
            -1: 'Verify row counts after extraction.',
        },
    },
    '01_spatial.sql': {
        'title': 'Spatial: H3 Heatmap',
        'intro': 'Maps GPS points to H3 hexagonal cells using `SDO_UTIL.H3_KEY` and aggregates visit counts, avg HR, and avg speed per cell.',
        'query_intents': {},
    },
    '02_timeseries.sql': {
        'title': 'Time Series: Gap Fill, Smooth, Detect',
        'intro': 'Demonstrates gap filling with `LAST_VALUE IGNORE NULLS`, moving-average smoothing, 30-second bucketing, and automatic interval detection on the 3\u00d72 km workout.',
        'query_intents': {},
    },
    '03_vector.sql': {
        'title': 'Vector: Effort Signatures & kNN',
        'intro': 'Builds an 11-dimensional effort fingerprint per run (HR zone %, normalised speed/HR, speed CV, pace zone %) and uses `VECTOR_DISTANCE(COSINE)` for similarity search.',
        'query_intents': {},
    },
    '04_graph.sql': {
        'title': 'Graph: SQL/PGQ Property Graph',
        'intro': 'Models runs and samples as a property graph. Uses `MATCH` to traverse routes and find crossed paths between runs.',
        'query_intents': {},
    },
    '05_json.sql': {
        'title': 'JSON-Relational Duality Views',
        'intro': 'Exposes normalised tables as JSON documents. Applications choose the shape; the database keeps one source of truth.',
        'query_intents': {},
    },
    '06_relational.sql': {
        'title': 'Relational: Domains, GROUP BY Alias, Integrity',
        'intro': 'Four sub-demos showing 23ai relational features: multi-paradigm access, SQL domains, GROUP BY alias, and constraint-based data quality.',
        'query_intents': {},
    },
}


def main():
    conn = oracledb.connect(
        user=os.getenv("ORA_USER"),
        password=os.getenv("ORA_PASSWORD"),
        dsn=os.getenv("ORA_DSN"),
    )

    scripts = [
        "sql/01_spatial.sql",
        "sql/02_timeseries.sql",
        "sql/03_vector.sql",
        "sql/04_graph.sql",
        "sql/05_json.sql",
        "sql/06_relational.sql",
    ]

    md = []
    md.append("# Strava Oracle Demo — Execution Results\n")
    md.append("All scripts executed against Oracle 26ai (`gvenzl/oracle-free`).  ")
    md.append("Output capped at 15 rows per query.\n")

    for script_path in scripts:
        base = os.path.basename(script_path)
        meta = SCRIPT_META.get(base, {})
        title = meta.get('title', base)
        intro = meta.get('intro', '')
        intents = meta.get('query_intents', {})

        md.append(f"\n---\n")
        md.append(f"## {base} — {title}\n")
        if intro:
            md.append(f"{intro}\n")

        root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(root, script_path)
        with open(path, 'r') as f:
            text = f.read()

        stmts = split_sql(text)

        for i, stmt in enumerate(stmts):
            intent = intents.get(i, '')
            sql_display = clean_sql(stmt)

            # Truncate long SQL for display
            sql_lines = sql_display.split('\n')
            if len(sql_lines) > 20:
                sql_display = '\n'.join(sql_lines[:18]) + '\n    -- ... (truncated)'

            try:
                cur = conn.cursor()
                cur.execute(stmt)

                if cur.description:
                    cols = [d[0] for d in cur.description]
                    rows = cur.fetchall()
                    table_str = format_table(cols, rows, max_rows=15)

                    if intent:
                        md.append(f"\n### Query {i+1}: {intent}\n")
                    else:
                        md.append(f"\n### Query {i+1}\n")

                    md.append(f"```sql\n{sql_display}\n```\n")
                    md.append(f"**Result** ({len(rows)} row{'s' if len(rows) != 1 else ''}):\n")
                    md.append(f"```\n{table_str}\n```\n")
                else:
                    if intent:
                        md.append(f"\n### Statement {i+1}: {intent}\n")
                    else:
                        md.append(f"\n### Statement {i+1}\n")
                    md.append(f"```sql\n{sql_display}\n```\n")
                    md.append(f"**Result:** OK\n")

                cur.close()
            except Exception as e:
                err = str(e).split('\n')[0]
                if intent:
                    md.append(f"\n### Statement {i+1}: {intent}\n")
                else:
                    md.append(f"\n### Statement {i+1}\n")
                md.append(f"```sql\n{sql_display}\n```\n")
                md.append(f"**Error:** `{err}`\n")

        conn.commit()

    # Domain constraint validation section
    md.append(f"\n---\n")
    md.append(f"## Domain Constraint Validation\n")
    md.append(f"Domains enforce semantic rules at the SQL level. Invalid values are rejected immediately.\n")

    domain_tests = [
        ("CAST(999 AS bpm_domain)",       "999 bpm — exceeds 0–300 range",        True),
        ("CAST(150 AS bpm_domain)",       "150 bpm — valid",                       False),
        ("CAST(999 AS latitude_domain)",  "999° latitude — exceeds -90..90",       True),
        ("CAST(-1 AS speed_kmh_domain)",  "negative speed — violates ≥ 0",         True),
        ("CAST(5 AS altitude_domain)",    "5 km altitude — valid",                 False),
        ("CAST(10 AS altitude_domain)",   "10 km altitude — exceeds -0.5..9.0",   True),
    ]

    md.append("| Expression | Intent | Result |")
    md.append("|---|---|---|")
    cur = conn.cursor()
    for expr, intent, expect_fail in domain_tests:
        try:
            cur.execute(f"SELECT {expr} FROM dual")
            val = cur.fetchone()[0]
            result = f"OK — returned `{val}`"
        except oracledb.DatabaseError as e:
            err_code = str(e).split(':')[0].strip()
            result = f"`{err_code}` — domain constraint rejected"
        md.append(f"| `{expr}` | {intent} | {result} |")
    cur.close()
    md.append("")

    conn.close()

    # Write results.md
    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results.md")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    print(f"Written {out_path}  ({len(md)} lines)")


if __name__ == "__main__":
    main()
