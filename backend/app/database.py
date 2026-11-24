"""Small, process-local SQLite database with atomic schema migrations."""

from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3
import stat
import sys
import threading
from collections.abc import Iterator


def default_database_path() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys_platform() == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "MOSAIC" / "mosaic.sqlite3"


def sys_platform() -> str:
    return sys.platform


class Database:
    """One SQLite connection serialized by a thread lock."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        if self.path != ":memory:":
            location = Path(self.path).expanduser()
            parent_existed = location.parent.exists()
            location.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if location.is_symlink():
                raise ValueError("MOSAIC_DB_PATH must not be a symbolic link")
            if location.exists() and not stat.S_ISREG(location.stat().st_mode):
                raise ValueError("MOSAIC_DB_PATH must refer to a regular file")
            try:
                if not parent_existed:
                    location.parent.chmod(0o700)
            except OSError:
                pass
            self.path = str(location)
            flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.path, flags, 0o600)
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise ValueError("MOSAIC_DB_PATH must refer to a regular file")
                try:
                    os.fchmod(descriptor, 0o600)
                except (AttributeError, OSError):
                    pass
            finally:
                os.close(descriptor)
        self.connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA busy_timeout = 10000")
        self.migrate()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                yield self.connection
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

    def migrate(self) -> None:
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                version = self.connection.execute("PRAGMA user_version").fetchone()[0]
                if version < 1:
                    script = """
                    CREATE TABLE conversations (
                        id TEXT PRIMARY KEY,
                        model TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE conversation_messages (
                        conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                        seq INTEGER NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        PRIMARY KEY(conversation_id, seq)
                    );
                    CREATE TABLE notes (
                        id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
                        category TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                    );
                    CREATE INDEX notes_title_idx ON notes(title);
                    CREATE TABLE subjects (
                        id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT,
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                    );
                    CREATE TABLE topics (
                        id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                        name TEXT NOT NULL, description TEXT, status TEXT NOT NULL DEFAULT 'not_started'
                            CHECK(status IN ('not_started', 'in_progress', 'completed')),
                        progress INTEGER CHECK(progress IS NULL OR (progress >= 0 AND progress <= 100)),
                        revision_date TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                        UNIQUE(subject_id, name)
                    );
                    CREATE TABLE memories (
                        id TEXT PRIMARY KEY, text TEXT NOT NULL CHECK(length(text) <= 4000),
                        category TEXT, source TEXT, enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
                        importance INTEGER CHECK(importance IS NULL OR (importance >= 1 AND importance <= 5)),
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                    );
                    CREATE INDEX memories_enabled_idx ON memories(enabled, updated_at DESC);
                    PRAGMA user_version = 1;
                    """
                    for statement in script.split(";"):
                        if statement.strip():
                            self.connection.execute(statement)
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self.connection.close()


__all__ = ["Database", "default_database_path"]
