# app/database.py

**用途**：建立 async DB engine，提供 FastAPI session dependency。

## 匯出

| 名稱 | 型別 | 說明 |
|------|------|------|
| `engine` | `AsyncEngine` | `create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)` |
| `AsyncSessionLocal` | `async_sessionmaker[AsyncSession]` | `expire_on_commit=False` |
| `get_db()` | `AsyncGenerator[AsyncSession]` | FastAPI dependency，`async with AsyncSessionLocal() as session: yield session` |

## 依賴

- `app.core.config.settings`（提供 `database_url`）

## 使用方式

```python
from app.database import get_db
# FastAPI endpoint 注入
async def endpoint(db: AsyncSession = Depends(get_db)): ...
```
