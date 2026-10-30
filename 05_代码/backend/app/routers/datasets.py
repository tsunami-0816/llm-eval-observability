"""评测集与 case CRUD。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_db
from app.models import EvalCase, EvalDataset

router = APIRouter()


@router.post("/datasets")
async def create_dataset(body: schemas.DatasetCreate, db: AsyncSession = Depends(get_db)):
    ds = EvalDataset(**body.model_dump())
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return {"code": 0, "data": {"id": ds.id}, "message": "ok"}


@router.get("/datasets")
async def list_datasets(project_id: int = 1, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EvalDataset).where(EvalDataset.project_id == project_id)
    )
    datasets = result.scalars().all()
    return {
        "code": 0,
        "data": [{"id": d.id, "name": d.name, "description": d.description} for d in datasets],
        "message": "ok",
    }


@router.post("/datasets/{dataset_id}/cases")
async def import_cases(
    dataset_id: int,
    body: schemas.CaseBatchIn,
    db: AsyncSession = Depends(get_db),
):
    imported = 0
    for c in body.cases:
        if not c.get("input"):
            continue
        db.add(EvalCase(
            dataset_id=dataset_id,
            input=c["input"],
            expected_output=c.get("expected_output", ""),
            scoring_criteria=c.get("scoring_criteria", ""),
        ))
        imported += 1
    await db.commit()
    return {"code": 0, "data": {"imported": imported}, "message": "ok"}


@router.get("/datasets/{dataset_id}/cases")
async def list_cases(dataset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvalCase).where(EvalCase.dataset_id == dataset_id))
    cases = result.scalars().all()
    return {
        "code": 0,
        "data": [
            {"id": c.id, "input": c.input, "expected_output": c.expected_output,
             "scoring_criteria": c.scoring_criteria}
            for c in cases
        ],
        "message": "ok",
    }
