"""SQLAlchemy models and database operations."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, Float, String, Text,
    create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config.settings import settings


class Base(DeclarativeBase):
    pass


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True)
    place_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    phone = Column(String)
    address = Column(Text)
    city = Column(String)
    state = Column(String, nullable=False)
    category = Column(String)
    sector_query = Column(String)
    website = Column(String)
    website_status = Column(String, default="none")  # none | social_only | parked_or_dead | active
    rating = Column(Float)
    reviews_count = Column(Integer)
    photo_count = Column(Integer)
    google_maps_url = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    # Scoring
    score = Column(Integer, default=0)
    score_breakdown = Column(Text)  # JSON string
    google_checked = Column(Boolean, default=False)
    google_confirmed_no_site = Column(Boolean, default=False)
    # Tracking
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    contacted = Column(Boolean, default=False)
    notes = Column(Text)


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True)
    search_term = Column(String, nullable=False)
    region = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending | in_progress | done | error
    result_count = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = create_engine(settings.database_url, echo=False)
event.listen(engine, "connect", _set_sqlite_pragma)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()


def upsert_business(session: Session, data: dict) -> Business:
    """Insert or update a business by place_id."""
    existing = session.query(Business).filter_by(place_id=data["place_id"]).first()
    if existing:
        for key, value in data.items():
            if value is not None:
                setattr(existing, key, value)
        session.commit()
        return existing
    biz = Business(**data)
    session.add(biz)
    session.commit()
    return biz


def get_or_create_job(session: Session, search_term: str, region: str) -> ScrapeJob:
    """Get existing job or create a new one."""
    job = (
        session.query(ScrapeJob)
        .filter_by(search_term=search_term, region=region)
        .first()
    )
    if job is None:
        job = ScrapeJob(search_term=search_term, region=region)
        session.add(job)
        session.commit()
    return job


def mark_job_started(session: Session, job: ScrapeJob):
    job.status = "in_progress"
    job.started_at = datetime.now(timezone.utc)
    session.commit()


def mark_job_done(session: Session, job: ScrapeJob, result_count: int):
    job.status = "done"
    job.result_count = result_count
    job.finished_at = datetime.now(timezone.utc)
    session.commit()


def mark_job_error(session: Session, job: ScrapeJob, error: str):
    job.status = "error"
    job.error_message = error
    job.finished_at = datetime.now(timezone.utc)
    session.commit()
