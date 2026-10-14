"""Vercel/ASGI entrypoint; the existing Streamlit UI stays in app.py."""
import os
from pathlib import Path

if os.getenv("VERCEL"):
    # Hosted Python has no globally installed Node CLI. Use the same official API
    # endpoints verified against the installed TinyFish SDK instead.
    os.environ.setdefault("TINYFISH_TRANSPORT", "http")
    os.environ.setdefault("STREAMLIT_SERVER_MAX_UPLOAD_SIZE", "4")
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")

import streamlit as st
from fastapi import FastAPI

dashboard = st.App(Path(__file__).resolve().parent / "app.py")
app = FastAPI(lifespan=dashboard.lifespan(), docs_url=None, redoc_url=None)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "CareerPilot", "transport": os.getenv("TINYFISH_TRANSPORT", "cli")}


app.mount("/", dashboard)
