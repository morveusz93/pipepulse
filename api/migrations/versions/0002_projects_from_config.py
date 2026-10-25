"""projects from configuration: drop connections, mark demo projects explicitly

The GitLab URL, token and project list now come from the environment, so stored
connections (and encrypted tokens) are gone. Demo projects were the ones without a
connection; that becomes an explicit is_demo flag.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("is_demo", sa.Boolean(), server_default="false", nullable=False),
    )
    op.execute("UPDATE projects SET is_demo = connection_id IS NULL")
    op.drop_constraint("uq_projects_connection_id", "projects", type_="unique")
    op.drop_constraint("fk_projects_connection_id_connections", "projects", type_="foreignkey")
    op.drop_column("projects", "connection_id")
    op.drop_table("connections")
    op.create_unique_constraint(
        op.f("uq_projects_is_demo"), "projects", ["is_demo", "gitlab_project_id"]
    )


def downgrade() -> None:
    # Stored tokens can't be restored: real projects come back without a connection, which
    # the old schema reads as demo projects. Remove them or re-add connections afterwards.
    op.drop_constraint(op.f("uq_projects_is_demo"), "projects", type_="unique")
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
    op.add_column("projects", sa.Column("connection_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_projects_connection_id_connections"),
        "projects",
        "connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        op.f("uq_projects_connection_id"),
        "projects",
        ["connection_id", "gitlab_project_id"],
        postgresql_nulls_not_distinct=True,
    )
    op.drop_column("projects", "is_demo")
