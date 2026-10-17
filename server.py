"""CIT demonstration server: static frontend and SQLite-backed workflow API."""

import base64
import binascii
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("CIT_DB_PATH", ROOT / "data" / "cit.sqlite3"))
HOST = os.environ.get("CIT_HOST", "127.0.0.1")
PORT = int(os.environ.get("CIT_PORT", "4317"))
LOCK = Lock()
PRIORITIES = {"Routine", "Medium", "High", "Manual review"}
MAX_BODY = 3 * 1024 * 1024


def connection():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS studies (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            arrival INTEGER NOT NULL,
            clinical TEXT NOT NULL,
            score REAL,
            input_check INTEGER NOT NULL,
            status TEXT NOT NULL,
            age INTEGER,
            sex TEXT,
            image TEXT,
            override_priority TEXT,
            override_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            study_seq INTEGER NOT NULL REFERENCES studies(seq),
            title TEXT NOT NULL,
            detail TEXT NOT NULL,
            time TEXT NOT NULL
        );
        """)
        if db.execute("SELECT COUNT(*) FROM studies").fetchone()[0]:
            return
        now = int(time.time() * 1000)
        samples = [
            (11, 108, "High", .81, 1, "Reviewed", 72, "M"),
            (12, 95, "Routine", .08, 1, "Reviewed", 33, "F"),
            (13, 82, "Routine", .13, 1, "Awaiting review", 45, "M"),
            (14, 61, "Routine", .22, 1, "Awaiting review", 61, "F"),
            (15, 44, "Medium", .51, 1, "Awaiting review", 38, "M"),
            (16, 29, "Routine", None, 0, "Awaiting review", 42, "F"),
            (17, 16, "High", .72, 1, "Awaiting review", 67, "M"),
            (18, 7, "Routine", .89, 1, "Awaiting review", 54, "F"),
        ]
        db.executemany("""INSERT INTO studies
            (seq, arrival, clinical, score, input_check, status, age, sex)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(seq, now - mins * 60000, clinical, score, check, status, age, sex)
             for seq, mins, clinical, score, check, status, age, sex in samples])


def study_id(seq):
    return f"CXR-{seq:04d}"


def study_dict(row):
    item = {
        "id": study_id(row["seq"]), "arrival": row["arrival"],
        "clinical": row["clinical"], "score": row["score"],
        "check": bool(row["input_check"]), "status": row["status"],
    }
    if row["age"] is not None:
        item.update(age=row["age"], sex=row["sex"])
    if row["image"]:
        item["image"] = row["image"]
    if row["override_priority"]:
        item["override"] = {
            "priority": row["override_priority"],
            "reason": row["override_reason"],
        }
    return item


def snapshot(db):
    studies = db.execute("SELECT * FROM studies ORDER BY seq DESC").fetchall()
    events = db.execute("SELECT * FROM events ORDER BY seq DESC").fetchall()
    return {
        "cases": [study_dict(row) for row in studies],
        "events": [{"title": row["title"], "detail": row["detail"],
                    "id": study_id(row["study_seq"]), "time": row["time"]}
                   for row in events],
        "platform": {"architecture": os.uname().machine, "inference": "simulated"},
    }


def event(db, seq, title, detail):
    db.execute("INSERT INTO events (study_seq, title, detail, time) VALUES (?, ?, ?, ?)",
               (seq, title, detail, datetime.now(timezone.utc).isoformat()))


def suggested(row):
    if row["override_priority"]:
        return row["override_priority"]
    if not row["input_check"]:
        return "High" if row["clinical"] == "High" else "Manual review"
    rank = {"Routine": 0, "Medium": 1, "High": 2}
    return max((row["clinical"], "High" if row["score"] is not None and row["score"] >= .8
                else "Medium" if row["score"] is not None and row["score"] >= .5
                else "Routine"), key=lambda value: rank[value])


class Handler(BaseHTTPRequestHandler):
    def json_response(self, code, value):
        body = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/state":
            with connection() as db:
                return self.json_response(200, snapshot(db))
        if path == "/api/health":
            return self.json_response(200, {"status": "ok", "architecture": os.uname().machine,
                                            "inference": "simulated"})
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/index.html": ("index.html", "text/html; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                 "/style.css": ("style.css", "text/css; charset=utf-8"),
                 "/assets/chest-illustration.svg":
                     ("assets/chest-illustration.svg", "image/svg+xml")}
        if path not in files:
            return self.json_response(404, {"error": "Not found"})
        name, mime = files[path]
        content = (ROOT / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        path = urlsplit(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            return self.json_response(413, {"error": "Request must be 3 MB or smaller"})
        try:
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Expected an object")
            with LOCK, connection() as db:
                if path == "/api/studies/demo":
                    cur = db.execute("""INSERT INTO studies
                        (arrival, clinical, score, input_check, status, age, sex)
                        VALUES (?, 'Routine', .87, 1, 'Awaiting review', 48, 'F')""",
                        (int(time.time() * 1000),))
                    seq = cur.lastrowid
                    event(db, seq, "Demo study added",
                          "Fictional case added with a simulated score of 0.87.")
                elif path == "/api/studies/import":
                    clinical = data.get("clinical")
                    image = data.get("image", "")
                    if clinical not in {"Routine", "Medium", "High"}:
                        raise ValueError("Invalid clinical priority")
                    if not isinstance(image, str) or not image.startswith((
                            "data:image/png;base64,", "data:image/jpeg;base64,")):
                        raise ValueError("A PNG or JPEG image is required")
                    raw = base64.b64decode(image.split(",", 1)[1], validate=True)
                    if len(raw) > 2 * 1024 * 1024 or not raw:
                        raise ValueError("Image must be 2 MB or smaller")
                    if not (raw.startswith(b"\x89PNG\r\n\x1a\n") or
                            raw.startswith(b"\xff\xd8\xff")):
                        raise ValueError("Image content does not match PNG or JPEG")
                    cur = db.execute("""INSERT INTO studies
                        (arrival, clinical, score, input_check, status, image)
                        VALUES (?, ?, NULL, 0, 'Awaiting review', ?)""",
                        (int(time.time() * 1000), clinical, image))
                    seq = cur.lastrowid
                    event(db, seq, "Study image imported",
                          "Image awaiting manual review; no AI analysis performed.")
                else:
                    parts = path.strip("/").split("/")
                    if len(parts) != 4 or parts[:2] != ["api", "studies"] or not parts[2].startswith("CXR-"):
                        return self.json_response(404, {"error": "Not found"})
                    try:
                        seq = int(parts[2][4:])
                    except ValueError:
                        return self.json_response(404, {"error": "Not found"})
                    row = db.execute("SELECT * FROM studies WHERE seq=?", (seq,)).fetchone()
                    if row is None:
                        return self.json_response(404, {"error": "Study not found"})
                    if parts[3] == "override":
                        priority = data.get("priority")
                        reason = data.get("reason", "")
                        if priority not in PRIORITIES or not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 500:
                            raise ValueError("Choose a priority and give a reason of 5–500 characters")
                        previous = suggested(row)
                        db.execute("UPDATE studies SET override_priority=?, override_reason=? WHERE seq=?",
                                   (priority, reason.strip(), seq))
                        event(db, seq, "Review priority changed",
                              f"{previous} → {priority}. {reason.strip()}")
                    elif parts[3] == "review":
                        if row["status"] == "Reviewed":
                            return self.json_response(409, {"error": "Study already reviewed"})
                        db.execute("UPDATE studies SET status='Reviewed' WHERE seq=?", (seq,))
                        event(db, seq, "Study marked reviewed",
                              "Review completed by Demo reviewer.")
                    else:
                        return self.json_response(404, {"error": "Not found"})
                result = snapshot(db)
                result["changedId"] = study_id(seq)
            return self.json_response(200, result)
        except (ValueError, TypeError, binascii.Error) as exc:
            return self.json_response(400, {"error": str(exc)})


if __name__ == "__main__":
    initialize()
    print(f"CIT demo server on http://{HOST}:{PORT} ({os.uname().machine})", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
