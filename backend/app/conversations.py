"""In-memory conversation lifecycle and context selection."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


class ConversationNotFoundError(LookupError):
    pass


@dataclass
class Conversation:
    id: str
    model: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    messages: list[dict[str, str]] = field(default_factory=list)


class ConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}

    def create(self, model: str) -> Conversation:
        conversation = Conversation(id=str(uuid4()), model=model)
        self._conversations[conversation.id] = conversation
        return conversation

    def get(self, conversation_id: str) -> Conversation:
        try:
            return self._conversations[conversation_id]
        except KeyError as exc:
            raise ConversationNotFoundError("Conversation not found") from exc

    def reset(self, conversation_id: str) -> Conversation:
        conversation = self.get(conversation_id)
        conversation.messages.clear()
        return conversation

    def context(self, conversation: Conversation, user_message: str, limit: int) -> list[dict[str, str]]:
        prior = conversation.messages[-(limit - 1):]
        return [*prior, {"role": "user", "content": user_message}]

    def append_turn(self, conversation: Conversation, user_message: str, answer: str) -> None:
        conversation.messages.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": answer},
        ])
