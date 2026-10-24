"""Database schema.

- connections: a GitLab instance + encrypted token (one token covers many projects)
- projects:    tracked GitLab projects; connection_id is NULL for demo/seed projects
- pipelines:   full pipeline history — source of trends, fail rate and MTTR
- jobs:        failed jobs only, with the tail of their trace for the inline log viewer

Aggregates (success rate, avg duration, MTTR) are computed in SQL on read, not stored.
Statuses are plain text on purpose: GitLab adds new ones over time.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(255))
    token_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    # Last 4 chars of the token, for the masked UI display (glpat-****abcd).
    token_hint: Mapped[str] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    projects: Mapped[list["Project"]] = relationship(
        back_populates="connection", cascade="all, delete-orphan", passive_deletes=True
    )


class Project(Base):
    __tablename__ = "projects"
    # NULLS NOT DISTINCT so demo projects (connection_id IS NULL) can't be duplicated.
    __table_args__ = (
        UniqueConstraint("connection_id", "gitlab_project_id", postgresql_nulls_not_distinct=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE")
    )
    gitlab_project_id: Mapped[int] = mapped_column(BigInteger)
    path_with_namespace: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    web_url: Mapped[str] = mapped_column(String(500))
    default_branch: Mapped[str | None] = mapped_column(String(255))
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    connection: Mapped[Connection | None] = relationship(back_populates="projects")
    pipelines: Mapped[list["Pipeline"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class Pipeline(Base):
    __tablename__ = "pipelines"
    __table_args__ = (
        UniqueConstraint("project_id", "gitlab_pipeline_id"),
        # Pulse bar, trends, recent-first lists.
        Index("ix_pipelines_project_created", "project_id", "created_at"),
        # MTTR: next success after a failure on the same ref.
        Index("ix_pipelines_project_ref_created", "project_id", "ref", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    gitlab_pipeline_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32))
    ref: Mapped[str] = mapped_column(String(255))
    sha: Mapped[str] = mapped_column(String(40))
    source: Mapped[str | None] = mapped_column(String(64))
    commit_title: Mapped[str | None] = mapped_column(Text)
    duration_s: Mapped[int | None] = mapped_column(Integer)
    queued_duration_s: Mapped[int | None] = mapped_column(Integer)
    web_url: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="pipelines")
    failed_jobs: Mapped[list["Job"]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan", passive_deletes=True
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("pipeline_id", "gitlab_job_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id", ondelete="CASCADE"))
    gitlab_job_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(255))
    stage: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    failure_reason: Mapped[str | None] = mapped_column(String(100))
    duration_s: Mapped[int | None] = mapped_column(Integer)
    web_url: Mapped[str] = mapped_column(String(500))
    # Last N lines of the job trace, ANSI codes preserved for the log viewer.
    trace_tail: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pipeline: Mapped[Pipeline] = relationship(back_populates="failed_jobs")
