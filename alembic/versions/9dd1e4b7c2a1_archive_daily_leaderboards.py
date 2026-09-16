"""remove qualification and add completed challenge archives"""

from alembic import op
import sqlalchemy as sa


revision = "9dd1e4b7c2a1"
down_revision = "f10820aa102b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("daily_challenges", "threshold")
    op.add_column(
        "daily_challenges",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_column("submissions", "qualified")
    op.create_table(
        "archived_leaderboard",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("final_position", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("equation", sa.Text(), nullable=False),
        sa.Column("input_mode", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Float(), nullable=False),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["challenge_id"],
            ["daily_challenges.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "challenge_id",
            "final_position",
            name="uq_archived_leaderboard_position",
        ),
    )
    op.create_index(
        op.f("ix_archived_leaderboard_challenge_id"),
        "archived_leaderboard",
        ["challenge_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_archived_leaderboard_challenge_id"),
        table_name="archived_leaderboard",
    )
    op.drop_table("archived_leaderboard")
    op.add_column(
        "submissions",
        sa.Column(
            "qualified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "daily_challenges",
        sa.Column(
            "threshold",
            sa.Float(),
            nullable=False,
            server_default="0.01",
        ),
    )
    op.drop_column("daily_challenges", "archived_at")
    op.alter_column("submissions", "qualified", server_default=None)
    op.alter_column("daily_challenges", "threshold", server_default=None)
