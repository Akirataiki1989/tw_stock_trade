#!/bin/bash
# FastAPI server startup — for Synology Task Scheduler
# Trigger: Boot-up / manually

export PATH="/volume1/web/codeserver/.tools:$PATH"
export UV_CACHE_DIR=/volume1/web/codeserver/.uv-cache
export UV_DATA_DIR=/volume1/web/codeserver/.uv-data
export UV_PYTHON_INSTALL_DIR=/volume1/web/codeserver/.uv-python
export HOME=/volume1/web/codeserver

cd /volume1/web/codeserver/tw_stock_trade

exec /volume1/web/codeserver/.tools/uv run uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8090 \
    --workers 1 \
    >> /volume1/web/codeserver/tw_stock_trade/log/api.log 2>&1
