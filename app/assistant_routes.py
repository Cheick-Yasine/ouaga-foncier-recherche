"""Route HTTP de l'assistant conversationnel Ouaga Foncier."""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from openai import OpenAIError
from pydantic import BaseModel, Field

from app.assistant_service import (
    AssistantNotConfiguredError,
    ChatMessage,
    MCPAssistantError,
    run_assistant,
)


LOGGER = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/assistant", tags=["Assistant"])


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2_000)


class AssistantRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2_000)
    history: list[ConversationMessage] = Field(default_factory=list, max_length=30)
    max_age_days: Literal[7, 30, 90] = 30


class AssistantResponse(BaseModel):
    answer: str
    results: list[dict[str, Any]]
    mcp_used: bool
    model: str


@router.post("/message", response_model=AssistantResponse)
async def assistant_message(payload: AssistantRequest) -> AssistantResponse:
    try:
        outcome = await run_assistant(
            payload.message,
            [ChatMessage(item.role, item.content) for item in payload.history],
            max_age_days=payload.max_age_days,
        )
    except AssistantNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except MCPAssistantError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except OpenAIError as error:
        LOGGER.warning("assistant_openai_error type=%s", type(error).__name__)
        raise HTTPException(
            status_code=502,
            detail="Le cerveau conversationnel est temporairement indisponible.",
        ) from None

    return AssistantResponse(
        answer=outcome.answer,
        results=outcome.results,
        mcp_used=outcome.mcp_used,
        model=outcome.model,
    )
