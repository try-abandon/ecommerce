from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(StrEnum):
    TEXT = "text"
    OBJECT = "object"


class ChatMessageRequest(BaseModel):
    message_id: str = Field(min_length=4, max_length=80)
    type: MessageType
    content: dict[str, Any]