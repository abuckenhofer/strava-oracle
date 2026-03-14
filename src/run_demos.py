#!/usr/bin/env python3
"""Execute demo SQL scripts against Oracle and print results."""

import os, re, sys
import oracledb
from dotenv import load_dotenv

load_dotenv()

def split_sql(text):
    """Split SQL text into executable statements.

    Handles:
    - Regular statements ending with ;
    - PL/SQL blocks ending with /
    - Duality view CREATE statements with { } blocks
    - Skips comment-only blocks
    """
    # Remove block comments but keep string literals intact
    # We'll strip block comments first
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

    stmts = []
    buf = []
    brace_depth = 0

    for line in text.split('\n'):
        stripped = line.strip()

        # Skip pure comment / empty lines when buffer is empty
        if not buf and (not stripped or stripped.startswith('--')):
            continue

        # Track brace depth for duality views
        brace_depth += line.count('{') - line.count('}')

        buf.append(line)

        # Statement terminates with ; at brace depth 0
        if stripped.endswith(';') and brace_depth <= 0:
            stmt = '\n'.join(buf).strip()
            # Remove trailing ;
            stmt = stmt.rstrip(';').strip()
            if stmt and not all(
                l.strip().startswith('--') or not l.strip()
                for l in stmt.split('\n')
            ):
                stmts.append(stmt)
            buf = []
            brace_depth = 0
        # PL/SQL terminator
        elif stripped == '/':
            stmt = '\n'.join(buf[:-1]).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            brace_depth = 0

    # Anything left in buffer
    if buf:
        stmt = '\n'.join(buf).strip().rstrip(';').strip()
        if stmt and not all(
            l.strip().startswith('--') or not l.strip()
            for l in stmt.split('\n')
        ):
            stmts.append(stmt)

    return stmts


def describe_stmt(stmt):
    """Short description of a SQL statement."""
    s = stmt.lstrip()
    # Remove leading line comments
    while s.startswith('--'):
        s = s.split('\n', 1)[-1].lstrip() if '\n' in s else ''
    first = s[:120].replace('\n', ' ')
    return first


def run_script(conn, path):
    """Run a SQL script and print results for SELECT statements."""
    name = os.path.basename(path)
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    with open(path, 'r') as f:
        text = f.read()

    stmts = split_sql(text)
    select_count = 0
    error_count = 0

    for i, stmt in enumerate(stmts, 1):
        desc = describe_stmt(stmt)
        is_select = stmt.lstrip().upper().startswith('SELECT') or \
                    stmt.lstrip().upper().startswith('WITH')

        label = f"[{i}/{len(stmts)}]"

        try:
            cur = conn.cursor()
            cur.execute(stmt)

            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = cur.fetchmany(30)  # cap at 30 rows for display
                total = len(rows)

                select_count += 1
                print(f"\n{label} {desc[:80]}")

                # Column headers
                widths = [max(len(c), max((len(str(r[j])) for r in rows), default=0))
                          for j, c in enumerate(cols)]
                widths = [min(w, 30) for w in widths]  # cap width

                hdr = ' | '.join(c.ljust(widths[j])[:widths[j]] for j, c in enumerate(cols))
                sep = '-+-'.join('-'*widths[j] for j in range(len(cols)))
                print(f"  {hdr}")
                print(f"  {sep}")
                for row in rows:
                    line = ' | '.join(
                        str(v if v is not None else '').ljust(widths[j])[:widths[j]]
                        for j, v in enumerate(row)
                    )
                    print(f"  {line}")

                if total == 0:
                    print(f"  (no rows)")
                else:
                    print(f"  ({total} row{'s' if total != 1 else ''})")
            else:
                print(f"{label} OK  {desc[:70]}")

            cur.close()
        except Exception as e:
            err = str(e).split('\n')[0][:100]
            print(f"{label} ERROR  {desc[:50]}...")
            print(f"         {err}")
            error_count += 1

    conn.commit()
    print(f"\n  Summary: {len(stmts)} statements, {select_count} with results, {error_count} errors")
    return error_count


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

    root = os.path.dirname(os.path.dirname(__file__))
    total_errors = 0
    for script in scripts:
        path = os.path.join(root, script)
        total_errors += run_script(conn, path)

    print(f"\n{'='*60}")
    print(f"  All done. Total errors: {total_errors}")
    print(f"{'='*60}")

    conn.close()
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
