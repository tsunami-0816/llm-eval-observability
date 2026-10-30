"""MySQL 业务表模型（SQLAlchemy ORM）。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, DECIMAL, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    __tablename__ = "project"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    api_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromptVersion(Base):
    __tablename__ = "prompt_version"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    name: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvalDataset(Base):
    __tablename__ = "eval_dataset"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvalCase(Base):
    __tablename__ = "eval_case"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("eval_dataset.id"))
    input: Mapped[str] = mapped_column(Text)
    expected_output: Mapped[str] = mapped_column(Text, default="")
    scoring_criteria: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvalRun(Base):
    __tablename__ = "eval_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("eval_dataset.id"))
    prompt_a_id: Mapped[int] = mapped_column(ForeignKey("prompt_version.id"))
    prompt_b_id: Mapped[int] = mapped_column(ForeignKey("prompt_version.id"))
    status: Mapped[str] = mapped_column(Enum("running", "done", "failed"), default="running")
    score_a_avg: Mapped[float] = mapped_column(DECIMAL(5, 2), default=0)
    score_b_avg: Mapped[float] = mapped_column(DECIMAL(5, 2), default=0)
    total_cases: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EvalResult(Base):
    __tablename__ = "eval_result"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("eval_run.id"))
    case_id: Mapped[int] = mapped_column(ForeignKey("eval_case.id"))
    score_a: Mapped[float] = mapped_column(DECIMAL(5, 2), default=0)
    score_b: Mapped[float] = mapped_column(DECIMAL(5, 2), default=0)
    judge_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
