.PHONY: dev up down logs eval test lint

dev:
	uvicorn main:app --reload --port 8000

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

eval:
	python eval/run_eval.py

eval-smoke:
	python eval/run_eval.py --smoke

test:
	pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	ruff check app/ eval/ tests/

reindex:
	curl -s -X POST http://localhost:8000/v1/admin/reindex \
	  -H "X-Admin-Key: $$(grep ADMIN_API_KEY .env | cut -d= -f2)" | python -m json.tool

ingest-news:
	python -c "import asyncio; from app.ingestion.workers.news import ingest_news_from_supabase; asyncio.run(ingest_news_from_supabase())"
