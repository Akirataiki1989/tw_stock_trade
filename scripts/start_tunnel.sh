#!/bin/bash
# Cloudflare Tunnel startup — for Synology Task Scheduler
# Trigger: Boot-up / manually

export HOME=/volume1/web/codeserver
export PATH="/volume1/web/codeserver/.tools:$PATH"

exec /volume1/web/codeserver/.tools/cloudflared tunnel \
    --config /volume1/web/codeserver/.cloudflared/config.yml \
    run tw-stock-api \
    >> /volume1/web/codeserver/tw_stock_trade/log/tunnel.log 2>&1
