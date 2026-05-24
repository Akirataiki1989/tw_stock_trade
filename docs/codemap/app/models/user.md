# app/models/user.py

**用途**：定義 `public.users` ORM model，由 fastapi-users 管理。

## Classes

| Class | Table | 說明 |
|-------|-------|------|
| `User` | `public.users` | fastapi-users 管理，勿直接修改欄位 |

`User` 繼承自 `SQLAlchemyBaseUserTableUUID`，欄位由 fastapi-users 自動定義（無 `__table_args__`，schema 為 `public`）。

> 欄位規格 → [`schema/tables.md`](../../../schema/tables.md)

## 依賴

- `app.models.base.Base`
- `fastapi_users.db.SQLAlchemyBaseUserTableUUID`
