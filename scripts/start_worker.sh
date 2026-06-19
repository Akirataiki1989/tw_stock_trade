#!/bin/bash
# ARQ Worker startup — for Synology Task Scheduler
# Trigger: Boot-up / manually

export PATH="/volume1/web/codeserver/.tools:$PATH"
export UV_CACHE_DIR=/volume1/web/codeserver/.uv-cache
export UV_DATA_DIR=/volume1/web/codeserver/.uv-data
export UV_PYTHON_INSTALL_DIR=/volume1/web/codeserver/.uv-python
export HOME=/volume1/web/codeserver

cd /volume1/web/codeserver/tw_stock_trade

# Self-heal: rebuild .venv if it's missing/broken (recurring issue on this NAS)
if [ ! -x .venv/bin/python ] || [ ! -x .venv/bin/arq ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') .venv missing or broken, rebuilding..." \
        >> /volume1/web/codeserver/tw_stock_trade/log/worker.log
    rm -rf .venv
    /volume1/web/codeserver/.tools/uv sync --python 3.12 \
        >> /volume1/web/codeserver/tw_stock_trade/log/worker.log 2>&1
fi

# Wait for Redis to be ready
until /volume1/web/codeserver/.tools/uv run python -c \
    "import socket; s=socket.create_connection(('localhost',6379),timeout=2); s.close()" \
    2>/dev/null; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') waiting for Redis..." \
        >> /volume1/web/codeserver/tw_stock_trade/log/worker.log
    sleep 3
done
echo "$(date '+%Y-%m-%d %H:%M:%S') Redis ready, starting Worker..." \
    >> /volume1/web/codeserver/tw_stock_trade/log/worker.log

exec /volume1/web/codeserver/.tools/uv run arq app.worker.WorkerSettings \
    >> /volume1/web/codeserver/tw_stock_trade/log/worker.log 2>&1
