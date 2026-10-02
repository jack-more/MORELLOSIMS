"""Keep nba_sim.db under GitHub's 100 MB file limit: move old daily snapshot
history out of the database into compressed monthly archives.

mojo_snapshots and player_potential gain ~1,000 rows a day (~0.23 MB/day,
~40 MB between March and October 2026), while nothing reads them beyond the
latest snapshot (generate_frontend.py: MAX(snapshot_date); snapshot_daily.py:
today's rows). At that rate nba_sim.db (76 MB in Oct 2026) would pass 100 MB
around the end of December and every pipeline push would be rejected.

Each calendar month that ended more than RETENTION_DAYS ago is written to
db/archive/<table>_<YYYY-MM>.csv.gz (all columns, header row, gzip mtime 0 so
re-writing identical rows yields identical bytes) and deleted from the
table; the database is then VACUUMed. Lossless and idempotent: an existing
archive is merged with any rows still in the table before they are deleted.
Restore with pandas.read_csv(path).to_sql(table, conn, if_exists="append").
"""

import gzip
import io
import logging
import os
import sqlite3
from datetime import date, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

TABLES = ("mojo_snapshots", "player_potential")
KEYS = ["player_id", "snapshot_date"]
RETENTION_DAYS = 45


def archive_dir(db_path):
    return os.path.join(os.path.dirname(os.path.abspath(db_path)), "archive")


def _months_to_archive(conn, table, cutoff: date):
    months = [r[0] for r in conn.execute(f"SELECT DISTINCT substr(snapshot_date, 1, 7) FROM {table}")]
    out = []
    for m in months:
        y, mo = int(m[:4]), int(m[5:7])
        last = (date(y + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1))
        if last < cutoff:
            out.append(m)
    return sorted(out)


def _write_gz(df, path):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as f:
        f.write(df.to_csv(index=False).encode())
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(buf.getvalue())
    os.replace(tmp, path)


def archive_snapshots(db_path, today: date | None = None, retention_days: int = RETENTION_DAYS) -> dict:
    today = today or date.today()
    cutoff = today - timedelta(days=retention_days)
    out_dir = archive_dir(db_path)
    conn = sqlite3.connect(db_path)
    moved = {}
    try:
        for table in TABLES:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", [table]).fetchone():
                continue
            for m in _months_to_archive(conn, table, cutoff):
                rows = pd.read_sql_query(f"SELECT * FROM {table} WHERE substr(snapshot_date, 1, 7) = ?", conn,
                                         params=[m])
                path = os.path.join(out_dir, f"{table}_{m}.csv.gz")
                if os.path.exists(path):
                    old = pd.read_csv(path)
                    rows = pd.concat([old, rows]).drop_duplicates(subset=KEYS, keep="last")
                rows = rows.sort_values(KEYS).reset_index(drop=True)
                os.makedirs(out_dir, exist_ok=True)
                _write_gz(rows, path)
                # verify the file round-trips before deleting anything
                check = pd.read_csv(path)
                if len(check) != len(rows):
                    raise RuntimeError(f"archive {path} wrote {len(check)} of {len(rows)} rows")
                n = conn.execute(f"DELETE FROM {table} WHERE substr(snapshot_date, 1, 7) = ?", [m]).rowcount
                conn.commit()
                moved[f"{table}_{m}"] = n
        if moved:
            conn.execute("VACUUM")
    finally:
        conn.close()
    if moved:
        logger.info("Snapshot archive: moved %d rows (%s) to %s; DB now %.1f MB", sum(moved.values()),
                    ", ".join(f"{k}: {v}" for k, v in moved.items()), out_dir, os.path.getsize(db_path) / 1e6)
    return moved
