"""Authenticated local notes, learning records, and curated memories."""

from datetime import date, datetime, timezone
import re
import sqlite3
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.tools import require_local_token

router = APIRouter(dependencies=[Depends(require_local_token)])


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoteInput(Input):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=50_000)
    category: str | None = Field(default=None, max_length=80)


class SubjectInput(Input):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)


class TopicInput(Input):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    status: Literal["not_started", "in_progress", "completed"] = "not_started"
    progress: int | None = Field(default=None, ge=0, le=100)
    revision_date: date | None = None


class TopicPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    status: Literal["not_started", "in_progress", "completed"] | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    revision_date: date | None = None


class MemoryInput(Input):
    text: str = Field(min_length=1, max_length=4000)
    category: str | None = Field(default=None, max_length=80)
    source: str | None = Field(default=None, max_length=200)
    enabled: bool = True
    importance: int | None = Field(default=None, ge=1, le=5)


def _row(row):
    if row is None:
        return None
    result = dict(row)
    if "enabled" in result:
        result["enabled"] = bool(result["enabled"])
    return result


def _require_row(row):
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return _row(row)


def _terms(q: str) -> list[str]:
    return [term for term in re.findall(r"[\w-]+", q.casefold()) if len(term) > 1][:12]


@router.post("/notes", status_code=201)
async def create_note(body: NoteInput, request: Request):
    stamp, identity = now(), str(uuid4())
    with request.app.state.database.transaction() as conn:
        conn.execute("INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?)",
                     (identity, body.title, body.content, body.category, stamp, stamp))
        return _row(conn.execute("SELECT * FROM notes WHERE id = ?", (identity,)).fetchone())


@router.get("/notes")
async def list_notes(request: Request, q: str | None = Query(default=None, max_length=200),
                     limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    with request.app.state.database.transaction() as conn:
        if q:
            pattern = f"%{q}%"
            rows = conn.execute("SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? OR category LIKE ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                                (pattern, pattern, pattern, limit, offset)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM notes ORDER BY updated_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    return {"notes": [_row(row) for row in rows]}


@router.get("/notes/{note_id}")
async def get_note(note_id: str, request: Request):
    with request.app.state.database.transaction() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    return _require_row(row)


@router.put("/notes/{note_id}")
async def update_note(note_id: str, body: NoteInput, request: Request):
    with request.app.state.database.transaction() as conn:
        cursor = conn.execute("UPDATE notes SET title=?, content=?, category=?, updated_at=? WHERE id=?",
                              (body.title, body.content, body.category, now(), note_id))
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="Record not found")
        return _row(conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone())


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(note_id: str, request: Request):
    with request.app.state.database.transaction() as conn:
        cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="Record not found")
    return Response(status_code=204)


@router.post("/learning/subjects", status_code=201)
async def create_subject(body: SubjectInput, request: Request):
    identity, stamp = str(uuid4()), now()
    try:
        with request.app.state.database.transaction() as conn:
            conn.execute("INSERT INTO subjects VALUES (?, ?, ?, ?, ?)",
                         (identity, body.name, body.description, stamp, stamp))
            return _row(conn.execute("SELECT * FROM subjects WHERE id=?", (identity,)).fetchone())
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Subject already exists") from exc


@router.get("/learning/subjects")
async def list_subjects(request: Request, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    with request.app.state.database.transaction() as conn:
        rows = conn.execute("SELECT * FROM subjects ORDER BY name LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    return {"subjects": [_row(row) for row in rows]}


@router.get("/learning/subjects/{subject_id}")
async def get_subject(subject_id: str, request: Request):
    with request.app.state.database.transaction() as conn:
        row = conn.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
    return _require_row(row)


@router.put("/learning/subjects/{subject_id}")
async def update_subject(subject_id: str, body: SubjectInput, request: Request):
    with request.app.state.database.transaction() as conn:
        cursor = conn.execute("UPDATE subjects SET name=?, description=?, updated_at=? WHERE id=?",
                              (body.name, body.description, now(), subject_id))
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="Subject not found")
        return _row(conn.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone())


@router.post("/learning/subjects/{subject_id}/topics", status_code=201)
async def create_topic(subject_id: str, body: TopicInput, request: Request):
    identity, stamp = str(uuid4()), now()
    try:
        with request.app.state.database.transaction() as conn:
            if conn.execute("SELECT 1 FROM subjects WHERE id=?", (subject_id,)).fetchone() is None:
                raise HTTPException(status_code=404, detail="Subject not found")
            conn.execute("INSERT INTO topics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (identity, subject_id, body.name, body.description, body.status, body.progress,
                          body.revision_date.isoformat() if body.revision_date else None, stamp, stamp))
            return _row(conn.execute("SELECT * FROM topics WHERE id=?", (identity,)).fetchone())
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Topic already exists for this subject") from exc


@router.get("/learning/topics")
async def list_topics(request: Request, subject_id: str | None = None,
                      limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    with request.app.state.database.transaction() as conn:
        if subject_id:
            rows = conn.execute("SELECT * FROM topics WHERE subject_id=? ORDER BY name LIMIT ? OFFSET ?",
                                (subject_id, limit, offset)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM topics ORDER BY subject_id, name LIMIT ? OFFSET ?",
                                (limit, offset)).fetchall()
    return {"topics": [_row(row) for row in rows]}


@router.get("/learning/topics/{topic_id}")
async def get_topic(topic_id: str, request: Request):
    with request.app.state.database.transaction() as conn:
        row = conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
    return _require_row(row)


@router.patch("/learning/topics/{topic_id}")
async def update_topic(topic_id: str, body: TopicPatch, request: Request):
    updates = body.model_dump(exclude_unset=True)
    if any(updates.get(key) is None for key in ("name", "status") if key in updates):
        raise HTTPException(status_code=422, detail="Name and status cannot be null")
    if not updates:
        raise HTTPException(status_code=422, detail="At least one topic field is required")
    if "revision_date" in updates and updates["revision_date"] is not None:
        updates["revision_date"] = updates["revision_date"].isoformat()
    updates["updated_at"] = now()
    allowed = {"name", "description", "status", "progress", "revision_date", "updated_at"}
    assignments = ", ".join(f"{key}=?" for key in updates if key in allowed)
    with request.app.state.database.transaction() as conn:
        cursor = conn.execute(f"UPDATE topics SET {assignments} WHERE id=?", (*updates.values(), topic_id))
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="Topic not found")
        return _row(conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone())


@router.delete("/learning/topics/{topic_id}", status_code=204)
async def delete_topic(topic_id: str, request: Request):
    with request.app.state.database.transaction() as conn:
        cursor = conn.execute("DELETE FROM topics WHERE id=?", (topic_id,))
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="Topic not found")
    return Response(status_code=204)


@router.delete("/learning/subjects/{subject_id}", status_code=204)
async def delete_subject(subject_id: str, request: Request):
    with request.app.state.database.transaction() as conn:
        cursor = conn.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="Subject not found")
    return Response(status_code=204)


@router.post("/memories", status_code=201)
async def create_memory(body: MemoryInput, request: Request):
    identity, stamp = str(uuid4()), now()
    with request.app.state.database.transaction() as conn:
        conn.execute("INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (identity, body.text, body.category, body.source, int(body.enabled), body.importance, stamp, stamp))
        return _row(conn.execute("SELECT * FROM memories WHERE id=?", (identity,)).fetchone())


@router.get("/memories")
async def list_memories(request: Request, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    with request.app.state.database.transaction() as conn:
        rows = conn.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    return {"memories": [_row(row) for row in rows]}


@router.get("/memories/search")
async def search_memories(request: Request, q: str = Query(min_length=1, max_length=200), limit: int = Query(default=5, ge=1, le=20)):
    terms = _terms(q)
    if not terms:
        return {"memories": []}
    with request.app.state.database.transaction() as conn:
        rows = conn.execute("SELECT * FROM memories WHERE enabled=1 AND (" + " OR ".join("text LIKE ?" for _ in terms) + ") ORDER BY importance DESC, updated_at DESC LIMIT ?",
                            (*[f"%{term}%" for term in terms], limit)).fetchall()
    return {"memories": [_row(row) for row in rows]}


@router.get("/memories/{memory_id}")
async def get_memory(memory_id: str, request: Request):
    with request.app.state.database.transaction() as conn:
        row = conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
    return _require_row(row)


@router.put("/memories/{memory_id}")
async def update_memory(memory_id: str, body: MemoryInput, request: Request):
    with request.app.state.database.transaction() as conn:
        cursor = conn.execute("UPDATE memories SET text=?, category=?, source=?, enabled=?, importance=?, updated_at=? WHERE id=?",
                              (body.text, body.category, body.source, int(body.enabled), body.importance, now(), memory_id))
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="Memory not found")
        return _row(conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone())


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, request: Request):
    with request.app.state.database.transaction() as conn:
        cursor = conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="Memory not found")
    return Response(status_code=204)


def retrieve_memories(database, query: str, limit: int = 5) -> list[dict]:
    terms = _terms(query)
    if not terms:
        return []
    with database.transaction() as conn:
        rows = conn.execute("SELECT * FROM memories WHERE enabled=1 AND (" + " OR ".join("text LIKE ?" for _ in terms) + ") ORDER BY importance DESC, updated_at DESC LIMIT ?",
                            (*[f"%{term}%" for term in terms], limit)).fetchall()
    return [_row(row) for row in rows]
