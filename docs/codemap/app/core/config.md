# app/core/config.py

**用途**：全域設定，透過 pydantic-settings 讀取 `.env`，提供全域單例 `settings`。

## 匯出

| 名稱 | 型別 | 說明 |
|------|------|------|
| `settings` | `Settings` | 全域單例，`from app.core.config import settings` |
| `get_settings()` | `() → Settings` | 建立新實例（一般不直接呼叫） |

## Settings 欄位

| 欄位 | 型別 | 預設值 | 用途 |
|------|------|--------|------|
| `database_url` | `str` | — | asyncpg DSN |
| `redis_url` | `str` | `"redis://localhost:6379"` | ARQ / cache |
| `secret_key` | `str` | — | JWT 簽名 |
| `jwt_algorithm` | `str` | `"HS256"` | |
| `access_token_expire_minutes` | `int` | `1440` | 1 天 |
| `fernet_key` | `str` | — | API Key 加密（Fernet AES-256）|
| `fbs_account` | `str` | `""` | FBS 帳號 |
| `fbs_password` | `str` | `""` | FBS 密碼 |
| `fbs_cert_path` | `str` | `""` | FBS 憑證路徑 |
| `gemini_api_key` | `str` | `""` | Google AI |
| `langfuse_public_key` | `str` | `""` | Langfuse 監控 |
| `langfuse_secret_key` | `str` | `""` | |
| `langfuse_host` | `str` | `"https://cloud.langfuse.com"` | |

## 注意

`model_config` 宣告為 `SettingsConfigDict`，**不可加型別注解**，否則 pydantic-settings 會將其當成欄位。
