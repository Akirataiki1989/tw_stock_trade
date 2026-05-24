# alembic/env.py

**用途**：Alembic async migration 設定檔。

## 關鍵設定

| 設定項 | 值 | 說明 |
|--------|-----|------|
| `include_schemas` | `True` | 偵測 `market` / `trading` schema 的 table |
| `version_table_schema` | `"public"` | `alembic_version` 表存放於 `public` schema |
| engine | asyncpg | 以 `run_async_migrations()` 執行 |
| `target_metadata` | `Base.metadata` | 涵蓋所有 ORM model 定義的 metadata |

## 依賴

- `app.core.config.settings`（取得 `database_url`）
- `app.models.base.Base`（以及 user / market / portfolio 的 import，確保 model 載入到 metadata）
