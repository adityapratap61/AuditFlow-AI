"""Start AuditFlow AI:  python run.py   (env: HOST, PORT, RELOAD)"""
import os
from pathlib import Path

import uvicorn

if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)  # keeps the default SQLite file inside backend/
    uvicorn.run("app.main:app", host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")),
                reload=os.getenv("RELOAD", "").lower() in {"1", "true", "yes"})
