import json
import sqlite3
import time
import uuid

ACTIVE = ("running", "awaiting_approval", "cancelling")

class Store:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, created REAL NOT NULL, messages TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL, model_id TEXT,
                    status TEXT NOT NULL, created REAL NOT NULL, error TEXT);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    time REAL NOT NULL, type TEXT NOT NULL, data TEXT NOT NULL);
            """)
            db.execute("UPDATE runs SET status='interrupted' WHERE status IN ('running','awaiting_approval','cancelling')")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create_session(self, title="New task"):
        key = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO sessions VALUES (?,?,?,?)", (key, title[:100], time.time(), "[]"))
        return self.session(key)

    def sessions(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT id,title,created FROM sessions ORDER BY created DESC LIMIT 200")]

    def session(self, key):
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (key,)).fetchone()
        if not row:
            raise KeyError(key)
        result = dict(row)
        result["messages"] = json.loads(result["messages"])
        return result

    def save_messages(self, key, messages):
        with self.connect() as db:
            db.execute("UPDATE sessions SET messages=? WHERE id=?", (json.dumps(messages), key))

    def create_run(self, session_id, model_id):
        key = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO runs VALUES (?,?,?,?,?,NULL)", (key, session_id, model_id, "running", time.time()))
        return key

    def status(self, key, status, error=None):
        with self.connect() as db:
            db.execute("UPDATE runs SET status=?,error=? WHERE id=?", (status, json.dumps(error) if error else None, key))

    def event(self, key, kind, data):
        with self.connect() as db:
            db.execute("INSERT INTO events(run_id,time,type,data) VALUES(?,?,?,?)",
                       (key, time.time(), kind, json.dumps(data, ensure_ascii=False)))

    def run(self, key, after=0):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (key,)).fetchone()
            events = db.execute("SELECT * FROM events WHERE run_id=? AND seq>? ORDER BY seq LIMIT 200",
                                (key, after)).fetchall()
        if not row:
            raise KeyError(key)
        value = dict(row)
        value["error"] = json.loads(value["error"]) if value["error"] else None
        value["events"] = [{**dict(e), "data":json.loads(e["data"])} for e in events]
        return value

    def runs(self, session_id):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT id,status,model_id,created FROM runs WHERE session_id=? ORDER BY created DESC",
                                               (session_id,))]
