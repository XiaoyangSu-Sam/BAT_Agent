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
            columns = {row[1] for row in db.execute("PRAGMA table_info(sessions)")}
            if "allow_all_execution" not in columns:
                db.execute("ALTER TABLE sessions ADD COLUMN allow_all_execution INTEGER NOT NULL DEFAULT 0")
            if "approval_mode" not in columns:
                db.execute("ALTER TABLE sessions ADD COLUMN approval_mode TEXT")
            db.execute("UPDATE runs SET status='interrupted' WHERE status IN ('running','awaiting_approval','cancelling')")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create_session(self, title="New task", approval_mode=None):
        key = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO sessions(id,title,created,messages,approval_mode) VALUES (?,?,?,?,?)",
                       (key, title[:100], time.time(), "[]", approval_mode))
        return self.session(key)

    def sessions(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("""SELECT s.id,s.title,s.created,s.allow_all_execution,s.approval_mode,
                COALESCE((SELECT MAX(r.created) FROM runs r WHERE r.session_id=s.id),s.created) AS updated
                FROM sessions s ORDER BY updated DESC LIMIT 200""")]

    def set_approval_mode(self, key, mode):
        with self.connect() as db:
            changed = db.execute("UPDATE sessions SET approval_mode=?, allow_all_execution=0 WHERE id=?", (mode, key))
            if changed.rowcount != 1:
                raise KeyError(key)

    def set_execution_approval(self, key, allow_all):
        with self.connect() as db:
            changed = db.execute("UPDATE sessions SET allow_all_execution=? WHERE id=?", (int(allow_all), key))
            if changed.rowcount != 1:
                raise KeyError(key)

    def execution_allowed(self, key):
        with self.connect() as db:
            row = db.execute("SELECT allow_all_execution FROM sessions WHERE id=?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return bool(row[0])

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
