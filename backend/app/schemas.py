"""HTTP request and response schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    voice_mode: bool = False
    voice_tools: bool = True
    voice_language: Literal["auto", "en", "hi", "hinglish"] = "auto"
    reasoning: Literal["default", "low", "medium", "high"] = "default"
    message: str = Field(min_length=1, max_length=20_000)
    conversation_id: str | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)


class ChatResponse(BaseModel):
    conversation_id: str
    model: str
    response: str
    metrics: dict[str, Any]


class ConversationCreate(BaseModel):
    model: str | None = Field(default=None, min_length=1, max_length=200)


class ConversationModelRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)
