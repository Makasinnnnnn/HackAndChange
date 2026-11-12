from __future__ import annotations

from uuid import uuid4

from sqlalchemy import JSON, String, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Learner(Base):
    __tablename__ = "app_learners"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    last_query: Mapped[str] = mapped_column(String(1500), default="")


class Signal(Base):
    __tablename__ = "app_signals"
    __table_args__ = (UniqueConstraint("learner_id", "material_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    learner_id: Mapped[str] = mapped_column(String(64), index=True)
    material_id: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(String(30))


def make_engine(url: str):
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            options["poolclass"] = StaticPool
    engine = create_engine(url, **options)
    Base.metadata.create_all(engine)
    return engine


def signals(session: Session, learner_id: str) -> dict[str, str]:
    return {
        s.material_id: s.value for s in session.scalars(select(Signal).where(Signal.learner_id == learner_id))
    }
