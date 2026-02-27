import os

STRICT_MODE = os.getenv("COPILOT_STRICT_MODE", "false").lower() == "true"