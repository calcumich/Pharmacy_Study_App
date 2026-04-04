.PHONY: db-up db-migrate db-seed db-bootstrap db-reset

# Start the Postgres container and wait until it is ready to accept connections.
db-up:
	docker compose up -d db
	@echo "Waiting for Postgres to be ready..."
	@until docker compose exec db pg_isready -U app -d pharmdb -q; do sleep 1; done
	@echo "Postgres is ready."

# Apply Alembic revisions to the running database.
db-migrate:
	alembic upgrade head

# Seed starter drug/class data after migrations are applied.
db-seed:
	python scripts/seed_mock_data.py

# Full local bootstrap path for a fresh database.
db-bootstrap: db-up db-migrate db-seed

# Remove the Postgres container and named volume for a truly clean local DB.
db-reset:
	docker compose down -v
