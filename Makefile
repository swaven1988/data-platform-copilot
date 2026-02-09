.PHONY: api ui

api:
	uvicorn app.api.main:app --reload --port 8000

ui:
	streamlit run ui/streamlit_app.py

