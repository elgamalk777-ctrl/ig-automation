import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from database import init_db
from routes import webhook, dashboard, api

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

app = FastAPI(title="IG Comment-to-DM Automation")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(webhook.router)
app.include_router(dashboard.router)
app.include_router(api.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")
