from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.config import settings
from backend.database import engine, Base
from backend.middleware.rate_limiter import limiter
from backend.routers import auth, sync, chatbot, stock, users, notifications, crm, actions, audio

Base.metadata.create_all(bind=engine)

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    from backend.services.sync_service import run_scheduled_sync
    from backend.services.audio_service import preload_model

    scheduler.add_job(
        run_scheduled_sync,
        "interval",
        minutes=settings.sync_interval_minutes,
        id="sync_job",
        replace_existing=True,
    )
    scheduler.start()

    # Whisper es lento en el primer uso — lo precargamos en background
    # para que el evento loop no se bloquee y el primer usuario no espere.
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, preload_model)

    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Stock Chatbot MVP", version="0.2.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
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
app.include_router(actions.router)
app.include_router(audio.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "node_id": settings.node_id,
        "node_role": settings.node_role,
        "central_server": settings.central_server_url or None,
    }
