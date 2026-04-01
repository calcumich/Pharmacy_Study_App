.PHONY: db-up migrate stamp

# Start the Postgres container and wait until it is ready to accept connections.
db-up:
	docker compose up -d db
	@echo "Waiting for Postgres to be ready..."
	@until docker compose exec db pg_isready -U app -d pharmdb -q; do sleep 1; done
	@echo "Postgres is ready."

# Apply the three SQL migrations in order, then tell Alembic the schema is current.
# Requires the DB to be running (run 'make db-up' first).
# Pipe via -T so stdin is not a TTY, allowing file redirection to work correctly.
migrate:
	docker compose exec -T db psql -U app -d pharmdb < docs/db/migrations/001_core_schema.sql
	docker compose exec -T db psql -U app -d pharmdb < docs/db/migrations/002_user_study.sql
	docker compose exec -T db psql -U app -d pharmdb < docs/db/migrations/003_seed_attribute_types.sql
	$(MAKE) stamp

# Mark the current DB schema as up-to-date in Alembic's version table.
# Use this after applying migrations manually; run 'alembic upgrade head' for
# future Alembic-managed revisions instead.
stamp:
	alembic stamp head
