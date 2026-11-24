"""Shared Pydantic schemas for tool invocation and results."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EmptyInput(StrictInput):
    pass


class PathInput(StrictInput):
    path: str = Field(min_length=1, max_length=4096)


class SearchInput(StrictInput):
    root: str = Field(min_length=1, max_length=4096)
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=50, ge=1, le=100)


class ApplicationInput(StrictInput):
    application: str = Field(min_length=1, max_length=100)


class ObjectOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: dict[str, Any]
