"""create_core_schema

Revision ID: 8d50f2cb30e1
Revises: 
Create Date: 2026-04-01 19:36:27.023563

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '8d50f2cb30e1'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    op.execute("CREATE TYPE attribute_shape AS ENUM ('scalar', 'list', 'relational')")
    op.execute(
        "CREATE TYPE interaction_severity AS ENUM ('minor', 'moderate', 'major', 'contraindicated')"
    )

    op.execute(
        """
        CREATE TABLE drug_classes (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            parent_id UUID REFERENCES drug_classes(id) ON DELETE RESTRICT,
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_drug_classes_parent_id ON drug_classes(parent_id)")

    op.execute(
        """
        CREATE TABLE attribute_types (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            slug TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            shape attribute_shape NOT NULL,
            source_table TEXT NOT NULL,
            is_system BOOLEAN NOT NULL DEFAULT TRUE,
            display_order INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE drugs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name TEXT NOT NULL,
            generic_name TEXT,
            drug_class_id UUID REFERENCES drug_classes(id) ON DELETE RESTRICT,
            attributes JSONB NOT NULL DEFAULT '{}',
            search_vector TSVECTOR,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_drugs_search_vector ON drugs USING GIN(search_vector)")
    op.execute("CREATE INDEX idx_drugs_drug_class_id ON drugs(drug_class_id)")
    op.execute("CREATE INDEX idx_drugs_name_trgm ON drugs USING GIN(name gin_trgm_ops)")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION drugs_search_vector_update() RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', COALESCE(NEW.name, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.generic_name, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.attributes->>'moa', '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_drugs_search_vector
        BEFORE INSERT OR UPDATE ON drugs
        FOR EACH ROW EXECUTE FUNCTION drugs_search_vector_update()
        """
    )

    op.execute(
        """
        CREATE TABLE drug_indications (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            drug_id UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
            value TEXT NOT NULL,
            notes TEXT,
            UNIQUE (drug_id, value)
        )
        """
    )
    op.execute("CREATE INDEX idx_drug_indications_drug_id ON drug_indications(drug_id)")

    op.execute(
        """
        CREATE TABLE drug_adrs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            drug_id UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
            value TEXT NOT NULL,
            notes TEXT,
            UNIQUE (drug_id, value)
        )
        """
    )
    op.execute("CREATE INDEX idx_drug_adrs_drug_id ON drug_adrs(drug_id)")

    op.execute(
        """
        CREATE TABLE drug_metabolism (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            drug_id UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
            value TEXT NOT NULL,
            notes TEXT,
            UNIQUE (drug_id, value)
        )
        """
    )
    op.execute("CREATE INDEX idx_drug_metabolism_drug_id ON drug_metabolism(drug_id)")

    op.execute(
        """
        CREATE TABLE drug_interactions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            drug_a_id UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
            drug_b_id UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
            severity interaction_severity NOT NULL,
            description TEXT,
            details JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_ddi_canonical_order CHECK (drug_a_id < drug_b_id),
            UNIQUE (drug_a_id, drug_b_id)
        )
        """
    )
    op.execute("CREATE INDEX idx_ddi_drug_a ON drug_interactions(drug_a_id)")
    op.execute("CREATE INDEX idx_ddi_drug_b ON drug_interactions(drug_b_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS drug_interactions")
    op.execute("DROP TABLE IF EXISTS drug_metabolism")
    op.execute("DROP TABLE IF EXISTS drug_adrs")
    op.execute("DROP TABLE IF EXISTS drug_indications")
    op.execute("DROP TRIGGER IF EXISTS trg_drugs_search_vector ON drugs")
    op.execute("DROP FUNCTION IF EXISTS drugs_search_vector_update()")
    op.execute("DROP TABLE IF EXISTS drugs")
    op.execute("DROP TABLE IF EXISTS attribute_types")
    op.execute("DROP TABLE IF EXISTS drug_classes")
    op.execute("DROP TYPE IF EXISTS interaction_severity")
    op.execute("DROP TYPE IF EXISTS attribute_shape")
