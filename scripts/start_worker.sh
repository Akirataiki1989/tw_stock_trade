#!/bin/bash
# ARQ Worker startup — for Synology Task Scheduler
# Trigger: Boot-up / manually

export PATH="/volume1/web/codeserver/.tools:$PATH"
export UV_CACHE_DIR=/volume1/web/codeserver/.uv-cache
export UV_DATA_DIR=/volume1/web/codeserver/.uv-data
export UV_PYTHON_INSTALL_DIR=/volume1/web/codeserver/.uv-python
export HOME=/volume1/web/codeserver

cd /volume1/web/codeserver/tw_stock_trade

exec /volume1/web/codeserver/.tools/uv run arq app.worker.WorkerSettings \
    >> /volume1/web/codeserver/tw_stock_trade/log/worker.log 2>&1
