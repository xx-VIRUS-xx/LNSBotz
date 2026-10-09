"""Content Transformation Bot REST API."""
from typing import Literal
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from core.db import User
from core.auth import get_current_user_flexible
from .tasks import transform_content

router = APIRouter(prefix="/content", tags=["Content Transformation"])

InputType = Literal["youtube", "pdf_url", "article_url", "raw_text"]
OutputFormat = Literal[
    "linkedin_post", "twitter_thread", "summary", "quiz",
    "study_notes", "email_newsletter", "instagram_caption", "blog_outline"
]


class TransformRequest(BaseModel):
    input_type: InputType
    source: str
    output_format: OutputFormat
    options: dict | None = None
    async_mode: bool = False


class BatchTransformRequest(BaseModel):
    jobs: list[TransformRequest]


@router.post("/transform", summary="Transform content to a new format")
async def transform(
    req: TransformRequest,
    user: User = Depends(get_current_user_flexible),
):
    if req.async_mode:
        task = transform_content.delay(
            str(user.id), req.input_type, req.source, req.output_format, req.options
        )
        return {"task_id": task.id, "status": "queued"}

    # Synchronous path for quick inline use
    from .agent import ContentAgent
    import asyncio
    agent = ContentAgent(user_id=str(user.id))
    result = await agent.transform(req.input_type, req.source, req.output_format, req.options)
    return result


@router.post("/batch", summary="Batch transform multiple pieces of content")
async def batch_transform(
    req: BatchTransformRequest,
    user: User = Depends(get_current_user_flexible),
):
    """Queue all jobs asynchronously and return task IDs."""
    task_ids = []
    for job in req.jobs:
        task = transform_content.delay(
            str(user.id), job.input_type, job.source, job.output_format, job.options
        )
        task_ids.append(task.id)
    return {"queued": len(task_ids), "task_ids": task_ids}


@router.get("/formats", summary="List available output formats")
async def list_formats():
    from .prompts import TRANSFORMATION_PROMPTS
    return {"formats": list(TRANSFORMATION_PROMPTS.keys())}
