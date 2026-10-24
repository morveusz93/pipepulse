"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("token_hint", sa.String(length=4), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connections")),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=True),
        sa.Column("gitlab_project_id", sa.BigInteger(), nullable=False),
        sa.Column("path_with_namespace", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("web_url", sa.String(length=500), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["connections.id"],
            name=op.f("fk_projects_connection_id_connections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint(
            "connection_id",
            "gitlab_project_id",
            name=op.f("uq_projects_connection_id"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_table(
        "pipelines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("gitlab_pipeline_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ref", sa.String(length=255), nullable=False),
        sa.Column("sha", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("commit_title", sa.Text(), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column("queued_duration_s", sa.Integer(), nullable=True),
        sa.Column("web_url", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_pipelines_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipelines")),
        sa.UniqueConstraint(
            "project_id", "gitlab_pipeline_id", name=op.f("uq_pipelines_project_id")
        ),
    )
    op.create_index(
        "ix_pipelines_project_created", "pipelines", ["project_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_pipelines_project_ref_created",
        "pipelines",
        ["project_id", "ref", "created_at"],
        unique=False,
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pipeline_id", sa.Integer(), nullable=False),
        sa.Column("gitlab_job_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("stage", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_reason", sa.String(length=100), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column("web_url", sa.String(length=500), nullable=False),
        sa.Column("trace_tail", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["pipeline_id"],
            ["pipelines.id"],
            name=op.f("fk_jobs_pipeline_id_pipelines"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("pipeline_id", "gitlab_job_id", name=op.f("uq_jobs_pipeline_id")),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_index("ix_pipelines_project_ref_created", table_name="pipelines")
    op.drop_index("ix_pipelines_project_created", table_name="pipelines")
    op.drop_table("pipelines")
    op.drop_table("projects")
    op.drop_table("connections")
