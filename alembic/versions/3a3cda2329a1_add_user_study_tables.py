"""add_user_study_tables

Revision ID: 3a3cda2329a1
Revises: 8d50f2cb30e1
Create Date: 2026-04-02 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3a3cda2329a1"
down_revision: Union[str, None] = "8d50f2cb30e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE srs_card_state AS ENUM ('new', 'learning', 'review', 'relearning')")

    op.execute(
        """
        CREATE TABLE srs_state (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL,
            drug_id UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
            stability FLOAT,
            difficulty FLOAT,
            state srs_card_state NOT NULL DEFAULT 'new',
            due_date TIMESTAMPTZ,
            last_review TIMESTAMPTZ,
            review_count INT NOT NULL DEFAULT 0,
            srs_data JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, drug_id)
        )
        """
    )
    op.execute("CREATE INDEX idx_srs_state_user_id ON srs_state(user_id)")
    op.execute("CREATE INDEX idx_srs_state_due_date ON srs_state(due_date)")

    op.execute(
        """
        CREATE TABLE study_sessions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ended_at TIMESTAMPTZ,
            drug_ids_studied JSONB NOT NULL DEFAULT '[]',
            session_metadata JSONB NOT NULL DEFAULT '{}'
        )
        """
    )
    op.execute("CREATE INDEX idx_study_sessions_user_id ON study_sessions(user_id)")
    op.execute("CREATE INDEX idx_study_sessions_started_at ON study_sessions(started_at)")

    op.execute(
        """
        CREATE TABLE flashcard_state (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL,
            drug_id UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
            attribute_type_id UUID NOT NULL REFERENCES attribute_types(id) ON DELETE CASCADE,
            is_buried BOOLEAN NOT NULL DEFAULT FALSE,
            is_flagged BOOLEAN NOT NULL DEFAULT FALSE,
            user_note TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, drug_id, attribute_type_id)
        )
        """
    )
    op.execute("CREATE INDEX idx_flashcard_state_user_id ON flashcard_state(user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS flashcard_state")
    op.execute("DROP TABLE IF EXISTS study_sessions")
    op.execute("DROP TABLE IF EXISTS srs_state")
    op.execute("DROP TYPE IF EXISTS srs_card_state")
