"""Prompt 版本 CRUD。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_db
from app.models import PromptVersion

router = APIRouter()


@router.post("/prompts")
async def create_prompt(body: schemas.PromptCreate, db: AsyncSession = Depends(get_db)):
    prompt = PromptVersion(**body.model_dump())
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return {"code": 0, "data": {"id": prompt.id}, "message": "ok"}


@router.get("/prompts")
async def list_prompts(project_id: int = 1, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PromptVersion).where(PromptVersion.project_id == project_id)
    )
    prompts = result.scalars().all()
    return {
        "code": 0,
        "data": [
            {"id": p.id, "name": p.name, "version": p.version, "content": p.content,
             "description": p.description, "created_at": p.created_at.isoformat()}
            for p in prompts
        ],
        "message": "ok",
    }


@router.post("/prompts/rollback/{prompt_id}")
async def rollback_prompt(prompt_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PromptVersion).where(PromptVersion.id == prompt_id))
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="prompt not found")
    new_version = PromptVersion(
        project_id=original.project_id,
        name=original.name,
        version=f"{original.version}-rollback",
        content=original.content,
        description=f"rollback from {original.id}",
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)
    return {"code": 0, "data": {"id": new_version.id}, "message": "ok"}
