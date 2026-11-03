#!/bin/bash
set -e

echo "=================================================="
echo "🔧 Восстановление базы n8n и активация бота..."
echo "=================================================="

WORKDIR="/home/$USER/tork-bot"
cd "$WORKDIR"

# 1. Pull latest git code (nginx.conf and n8n_dump.sql)
echo "📥 [1/6] Подтягивание свежего кода из Git..."
git fetch origin manager-only-mode
git reset --hard origin/manager-only-mode

# 2. Setup real .env
echo "⚙️ [2/6] Запись боевых переменных окружения..."
VLM_KEY="${1:-}"
cat << EOF > .env
TELEGRAM_BOT_TOKEN=8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY
ALLOWED_TELEGRAM_IDS=5699064827,7390702902,1248663402
MANAGER_CHAT_ID=-100200300400
VLM_API_KEY=\${VLM_KEY}
IMAGE_EDIT_MODEL=gemini-3.1-flash-image
IMAGE_EDIT_API_KEY=\${VLM_KEY}
POSTGRES_USER=tork_admin
POSTGRES_PASSWORD=supersecret_tork_kz_pass
POSTGRES_DB=tork_bot_db
POSTGRES_PORT=5433
N8N_ENCRYPTION_KEY=tork-bot-kz-secret-encryption-key-2026
N8N_HOST=localhost
N8N_PORT=5678
N8N_PROTOCOL=http
GOTENBERG_URL=http://gotenberg:3000
JWT_SECRET=tork-b2b-dashboard-secret-jwt-key-2026
DEFAULT_DISTRIBUTOR_ID=1
EOF

# 3. Restore n8n database dump (credentials, users, workflow and webhooks)
echo "💾 [3/6] Восстановление настроек n8n в PostgreSQL..."
sudo docker exec -i tork_postgres psql -U tork_admin -d tork_bot_db < n8n_dump.sql

# 4. Get current Tunnel URL
echo "🌐 [4/6] Определение адреса туннеля..."
TUNNEL_URL=$(sudo docker logs cloudflared 2>&1 | grep -o 'https://[-a-zA-Z0-9.]*\.trycloudflare\.com' | head -n 1 || true)
if [ -z "$TUNNEL_URL" ]; then
    echo "Перезапуск cloudflared..."
    sudo docker rm -f cloudflared 2>/dev/null || true
    sudo docker run -d --name cloudflared --restart unless-stopped --network host cloudflare/cloudflared:latest tunnel --url http://localhost:8088
    sleep 5
    TUNNEL_URL=$(sudo docker logs cloudflared 2>&1 | grep -o 'https://[-a-zA-Z0-9.]*\.trycloudflare\.com' | head -n 1)
fi

echo "WEBHOOK_URL=$TUNNEL_URL" >> .env
echo "URL туннеля: $TUNNEL_URL"

# 5. Restart containers to load updated config and DB state
echo "🔄 [5/6] Перезапуск контейнеров..."
sudo docker compose restart

# 6. Re-register Telegram Webhook and Menu Button
echo "📲 [6/6] Привязка активного вебхука n8n в Telegram..."
SECRET_TOKEN="sHnoGT842oAJacFu_Telegram_Trigger"
WEBHOOK_TARGET="$TUNNEL_URL/webhook/6203b22d-7f6e-4731-b245-0f6a913edfa1/webhook"

curl -s -F "url=$WEBHOOK_TARGET" \
     -F "secret_token=$SECRET_TOKEN" \
     "https://api.telegram.org/bot8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY/setWebhook"

curl -s -X POST "https://api.telegram.org/bot8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY/setChatMenuButton" \
     -H "Content-Type: application/json" \
     -d "{\"menu_button\": {\"type\": \"web_app\", \"text\": \"✨ Каталог Tork\", \"web_app\": {\"url\": \"$TUNNEL_URL/webapp/\"}}}"

echo ""
echo "=================================================="
echo "🎉 ВСЁ ИСПРАВЛЕНО И АКТИВИРОВАНО!"
echo "👉 Откройте бота и отправьте /start"
echo "=================================================="
