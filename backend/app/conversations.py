"""SQLite-backed conversation lifecycle and context selection."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.database import Database


class ConversationNotFoundError(LookupError):
    pass


@dataclass
class Conversation:
    id: str
    model: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    messages: list[dict[str, str]] = field(default_factory=list)


class ConversationStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, model: str) -> Conversation:
        conversation = Conversation(id=str(uuid4()), model=model)
        with self.database.transaction() as conn:
            conn.execute(
                "INSERT INTO conversations(id, model, created_at) VALUES (?, ?, ?)",
                (conversation.id, model, conversation.created_at.isoformat()),
            )
        return conversation

    def get(self, conversation_id: str) -> Conversation:
        with self.database.transaction() as conn:
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            if row is None:
                raise ConversationNotFoundError("Conversation not found")
            messages = conn.execute(
                "SELECT role, content FROM conversation_messages WHERE conversation_id = ? ORDER BY seq",
                (conversation_id,),
            ).fetchall()
        return Conversation(
            id=row["id"], model=row["model"],
            created_at=datetime.fromisoformat(row["created_at"]),
            messages=[{"role": item["role"], "content": item["content"]} for item in messages],
        )

    def reset(self, conversation_id: str) -> Conversation:
        conversation = self.get(conversation_id)
        with self.database.transaction() as conn:
            conn.execute("DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,))
        conversation.messages.clear()
        return conversation

    def set_model(self, conversation_id: str, model: str) -> Conversation:
        with self.database.transaction() as conn:
            cursor = conn.execute("UPDATE conversations SET model = ? WHERE id = ?", (model, conversation_id))
            if cursor.rowcount != 1:
                raise ConversationNotFoundError("Conversation not found")
        return self.get(conversation_id)

    def delete(self, conversation_id: str) -> None:
        with self.database.transaction() as conn:
            cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            if cursor.rowcount != 1:
                raise ConversationNotFoundError("Conversation not found")

    def list(self, limit: int, offset: int) -> list[dict[str, str]]:
        with self.database.transaction() as conn:
            rows = conn.execute(
                "SELECT id, model, created_at FROM conversations ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def context(self, conversation: Conversation, user_message: str, limit: int) -> list[dict[str, str]]:
        prior = conversation.messages[-(limit - 1):]
        return [*prior, {"role": "user", "content": user_message}]

    def append_turn(self, conversation: Conversation, user_message: str, answer: str) -> None:
        with self.database.transaction() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM conversation_messages WHERE conversation_id = ?",
                (conversation.id,),
            ).fetchone()
            seq = row[0]
            conn.executemany(
                "INSERT INTO conversation_messages(conversation_id, seq, role, content) VALUES (?, ?, ?, ?)",
                ((conversation.id, seq + 1, "user", user_message),
                 (conversation.id, seq + 2, "assistant", answer)),
            )
        conversation.messages.extend([
            {"role": "user", "content": user_message}, {"role": "assistant", "content": answer}
        ])
