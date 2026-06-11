"""Replace btree unique constraints on list table value columns with md5 functional indexes.

The original UNIQUE (drug_id, value) constraints use a btree index on the raw TEXT value.
Postgres btree indexes have a hard limit of ~2704 bytes per entry. openFDA ADR and indication
text can exceed this, causing ProgramLimitExceededError on insert. MD5 hashing the value
column keeps uniqueness semantics while staying well within the size limit.

Revision ID: b9c1e2f3a4d5
Revises: f5ef1a0d7d64
Create Date: 2026-06-11
"""

from typing import Union

from alembic import op

revision: str = "b9c1e2f3a4d5"
down_revision: Union[str, None] = "f5ef1a0d7d64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE drug_indications
            DROP CONSTRAINT IF EXISTS drug_indications_drug_id_value_key
    """)
    op.execute("""
        ALTER TABLE drug_adrs
            DROP CONSTRAINT IF EXISTS drug_adrs_drug_id_value_key
    """)
    op.execute("""
        ALTER TABLE drug_metabolism
            DROP CONSTRAINT IF EXISTS drug_metabolism_drug_id_value_key
    """)

    op.execute("""
        CREATE UNIQUE INDEX drug_indications_drug_id_value_hash_key
            ON drug_indications (drug_id, md5(value))
    """)
    op.execute("""
        CREATE UNIQUE INDEX drug_adrs_drug_id_value_hash_key
            ON drug_adrs (drug_id, md5(value))
    """)
    op.execute("""
        CREATE UNIQUE INDEX drug_metabolism_drug_id_value_hash_key
            ON drug_metabolism (drug_id, md5(value))
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS drug_indications_drug_id_value_hash_key")
    op.execute("DROP INDEX IF EXISTS drug_adrs_drug_id_value_hash_key")
    op.execute("DROP INDEX IF EXISTS drug_metabolism_drug_id_value_hash_key")

    op.execute("""
        ALTER TABLE drug_indications ADD CONSTRAINT drug_indications_drug_id_value_key
            UNIQUE (drug_id, value)
    """)
    op.execute("""
        ALTER TABLE drug_adrs ADD CONSTRAINT drug_adrs_drug_id_value_key
            UNIQUE (drug_id, value)
    """)
    op.execute("""
        ALTER TABLE drug_metabolism ADD CONSTRAINT drug_metabolism_drug_id_value_key
            UNIQUE (drug_id, value)
    """)
