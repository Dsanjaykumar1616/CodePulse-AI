"""Initial schema: users, repositories, analysis jobs and results.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "repositories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_url", sa.String(500), nullable=False),
        sa.Column("owner", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("last_analyzed_at", TS),
        sa.Column("health_score", sa.Float),
        sa.Column("debt_score", sa.Float),
        sa.Column("risk_signal", sa.Float),
        sa.UniqueConstraint("user_id", "canonical_url", name="uq_user_repo"),
    )
    op.create_index("ix_repositories_user_id", "repositories", ["user_id"])

    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("current_stage", sa.String(50)),
        sa.Column("progress", sa.Integer, nullable=False),
        sa.Column("stages", JSON, nullable=False),
        sa.Column("warnings", JSON, nullable=False),
        sa.Column("error_code", sa.String(50)),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("started_at", TS),
        sa.Column("finished_at", TS),
    )
    op.create_index("ix_analysis_jobs_repository_id", "analysis_jobs", ["repository_id"])
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("overview", JSON, nullable=False),
        sa.Column("health", JSON, nullable=False),
        sa.Column("risk", JSON, nullable=False),
        sa.Column("debt", JSON, nullable=False),
        sa.Column("duplicates", JSON, nullable=False),
        sa.Column("architecture", JSON, nullable=False),
        sa.Column("review", JSON, nullable=False),
        sa.Column("issues", JSON, nullable=False),
        sa.Column("opportunities", JSON, nullable=False),
        sa.Column("files", JSON, nullable=False),
        sa.Column("report_html", sa.Text),
    )
    op.create_index("ix_analysis_results_job_id", "analysis_results", ["job_id"], unique=True)


def downgrade() -> None:
    op.drop_table("analysis_results")
    op.drop_table("analysis_jobs")
    op.drop_table("repositories")
    op.drop_table("users")
