from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from app.models.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
