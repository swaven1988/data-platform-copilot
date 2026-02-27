from app.api.main import app

if __name__ == "__main__":
    import os
    import uvicorn
    host = os.getenv("COPILOT_HOST", "0.0.0.0")
    port = int(os.getenv("COPILOT_PORT", "8001"))
    uvicorn.run(app, host=host, port=port)