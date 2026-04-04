"""seed_attribute_types

Revision ID: f5ef1a0d7d64
Revises: 3a3cda2329a1
Create Date: 2026-04-02 21:11:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f5ef1a0d7d64"
down_revision: Union[str, None] = "3a3cda2329a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO attribute_types (slug, label, shape, source_table, is_system, display_order)
        VALUES
            ('moa', 'Mechanism of Action', 'scalar', 'drugs', TRUE, 1),
            ('half_life', 'Half-life', 'scalar', 'drugs', TRUE, 2),
            ('indications', 'Indications', 'list', 'drug_indications', TRUE, 3),
            ('adrs', 'Adverse Drug Reactions', 'list', 'drug_adrs', TRUE, 4),
            ('metabolism', 'Metabolism / CYP', 'list', 'drug_metabolism', TRUE, 5),
            ('ddis', 'Major Drug Interactions', 'relational', 'drug_interactions', TRUE, 6)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM attribute_types
        WHERE slug IN ('moa', 'half_life', 'indications', 'adrs', 'metabolism', 'ddis')
        """
    )
