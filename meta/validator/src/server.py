"""HTTP API for running goldador validation against a remote Git ref."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from meta.validator.src.github_utils import (
    GOLDADOR_REPO_FULL_NAME,
    GoldadorGitHubError,
)
from meta.validator.src.remote_validation import run_remote_validation
from meta.validator.src.rules.members import MemberValidationError
from meta.validator.src.rules.teams import TeamValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Load environment before handling requests."""
    load_dotenv()
    yield


app = FastAPI(title="Goldador validator", lifespan=lifespan)


class ValidateRequest(BaseModel):
    """Request body for ``POST /validate``."""

    ref: str = Field(
        ...,
        min_length=1,
        max_length=260,
        description="Git ref (branch, tag, or SHA)",
    )


def run_validation_for_ref(ref: str) -> dict[str, Any]:
    """Fetch TOML from GitHub at ``ref`` and return structured validation results."""
    reporter, extras = run_remote_validation(ref)
    return {**extras, "validation": reporter.as_result()}


@app.get("/")
def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


@app.post("/validate")
async def validate_remote(body: ValidateRequest) -> dict[str, Any]:
    """Validate governance TOML at ``ref`` using the same rules as the CLI."""
    try:
        return await asyncio.to_thread(run_validation_for_ref, body.ref)
    except GoldadorGitHubError as e:
        raise HTTPException(
            status_code=e.status_code or 502,
            detail={
                "repository": GOLDADOR_REPO_FULL_NAME,
                "ref": body.ref,
                "error": e.message,
            },
        ) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "repository": GOLDADOR_REPO_FULL_NAME,
                "ref": body.ref,
                "error": str(e),
            },
        ) from e
    except MemberValidationError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "repository": GOLDADOR_REPO_FULL_NAME,
                "ref": body.ref,
                "error": e.message,
            },
        ) from e
    except TeamValidationError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "repository": GOLDADOR_REPO_FULL_NAME,
                "ref": body.ref,
                "error": e.message,
            },
        ) from e


def main() -> None:
    """Run the API with uvicorn (dev-friendly defaults)."""
    load_dotenv()
    uvicorn.run(
        "meta.validator.src.server:app",
        host="0.0.0.0",  # noqa: S104
        port=8000,
        reload=False,
    )
