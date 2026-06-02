from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.config import settings
from backend.database import engine, Base
from backend.middleware.rate_limiter import limiter
from backend.routers import auth, sync, chatbot, stock, users, notifications, crm

Base.metadata.create_all(bind=engine)

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.services.sync_service import run_scheduled_sync
    scheduler.add_job(
        run_scheduled_sync,
        "interval",
        minutes=settings.sync_interval_minutes,
        id="sync_job",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Stock Chatbot MVP", version="0.2.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sync.router)
app.include_router(chatbot.router)
app.include_router(stock.router)
app.include_router(users.router)
app.include_router(notifications.router)
app.include_router(crm.router)


@app.get("/health")
def health():
    return {"status": "ok"}
