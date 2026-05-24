from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.market import router as market_router
from app.api.portfolio import router as portfolio_router
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.users import auth_backend, fastapi_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB 由 Alembic 管理，不在此建立 table
    yield


app = FastAPI(title="TW Stock Trade API", lifespan=lifespan)

# Auth: POST /auth/jwt/login, POST /auth/jwt/logout
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

# Register: POST /auth/register
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

# Users: GET/PATCH /users/me, GET/PATCH /users/{id}
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

app.include_router(portfolio_router)
app.include_router(market_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
