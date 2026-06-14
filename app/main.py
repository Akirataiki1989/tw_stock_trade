from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI

from app.api.ai import router as ai_router
from app.api.market import router as market_router
from app.api.portfolio import router as portfolio_router
from app.api.ws import router as ws_router
from app.core.config import settings
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.users import auth_backend, fastapi_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.arq = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    yield
    await app.state.arq.aclose()


app = FastAPI(
    title="TW Stock Trade API",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
)

V1 = "/api/v1"

# Auth: POST /api/v1/auth/jwt/login, POST /api/v1/auth/jwt/logout
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix=f"{V1}/auth/jwt",
    tags=["auth"],
)

# Register: POST /api/v1/auth/register
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix=f"{V1}/auth",
    tags=["auth"],
)

# Users: GET/PATCH /api/v1/users/me, GET/PATCH /api/v1/users/{id}
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix=f"{V1}/users",
    tags=["users"],
)

app.include_router(portfolio_router, prefix=V1)
app.include_router(market_router, prefix=V1)
app.include_router(ai_router, prefix=V1)
app.include_router(ws_router)  # /ws/quotes, /ws/ai-stream (no version prefix)


@app.get("/health")
async def health():
    return {"status": "ok"}
