.PHONY: api ui snapshot verify-snapshot

api:
	uvicorn app.api.main:app --reload --port 8001

ui:
	streamlit run ui/streamlit_app.py

snapshot:
	@echo "Regenerating OpenAPI snapshot from local running server..."
	@curl -s http://127.0.0.1:8001/openapi.json > tests/snapshots/openapi_snapshot.json
	@python -m json.tool tests/snapshots/openapi_snapshot.json > tmp.json
	@mv tmp.json tests/snapshots/openapi_snapshot.json
	@echo "OpenAPI snapshot regenerated: tests/snapshots/openapi_snapshot.json"

verify-snapshot:
	@echo "Verifying OpenAPI snapshot..."
	@python -m pytest tests/test_openapi_snapshot.py -q
