#!/bin/bash
set -e

echo "=================================================="
echo "🔧 Полная диагностика и активация бота Tork..."
echo "=================================================="

WORKDIR="/home/$USER/tork-bot"
cd "$WORKDIR"

# 1. Update repo
echo "📥 [1/8] Обновление репозитория из ветки manager-only-mode..."
git fetch origin manager-only-mode
git reset --hard origin/manager-only-mode

# 2. Setup real .env
echo "⚙️ [2/8] Проверка переменных окружения..."
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

# 3. Restore n8n database dump (includes credentials, users, workflow and webhooks)
echo "💾 [3/8] Восстановление дампа базы данных n8n в PostgreSQL..."
sudo docker exec -i tork_postgres psql -U tork_admin -d tork_bot_db < n8n_dump.sql || true

# 4. Generate and import credentials
echo "🔑 [4/8] Импорт учетных записей Telegram и Postgres..."
cat << 'EOF' > workflows/credentials_import.json
[
  {
    "id": "ASiKmvQz4bYnK32G",
    "name": "Telegram account",
    "type": "telegramApi",
    "data": {
      "accessToken": "8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY"
    }
  },
  {
    "id": "ssRaEX0w25vYf2wI",
    "name": "Postgres account",
    "type": "postgres",
    "data": {
      "host": "postgres",
      "port": 5432,
      "database": "tork_bot_db",
      "user": "tork_admin",
      "password": "supersecret_tork_kz_pass",
      "schema": "public",
      "ssl": "disable"
    }
  }
]
EOF

sudo docker compose exec -u node n8n n8n import:credentials --input=/data/workflows/credentials_import.json || true
sudo docker compose exec -u node n8n n8n import:workflow --input=/data/workflows/tork_bot_workflow.json || true
sudo docker compose exec postgres psql -U tork_admin -d tork_bot_db -c "UPDATE workflow_entity SET active = true;"

# 5. Get current Tunnel URL
echo "🌐 [5/8] Определение адреса туннеля Cloudflare..."
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

# 6. Restart n8n, cdn and dashboard_api
echo "🔄 [6/8] Перезапуск контейнеров..."
sudo docker compose restart

echo "⏳ Ожидание полной инициализации n8n..."
sleep 10

# 7. Check active workflow ID & webhook path from DB
echo "🔍 [7/8] Чтение активного вебхука из базы данных..."
WF_ID=$(sudo docker compose exec -T postgres psql -U tork_admin -d tork_bot_db -t -c "SELECT id FROM workflow_entity WHERE active = true ORDER BY \"updatedAt\" DESC LIMIT 1;" | tr -d '[:space:]')
if [ -z "$WF_ID" ]; then
    WF_ID="sHnoGT842oAJacFu"
fi
echo "Активный Workflow ID: $WF_ID"

HOOK_PATH=$(sudo docker compose exec -T postgres psql -U tork_admin -d tork_bot_db -t -c "SELECT \"webhookPath\" FROM webhook_entity LIMIT 1;" | tr -d '[:space:]')
if [ -z "$HOOK_PATH" ]; then
    HOOK_PATH="6203b22d-7f6e-4731-b245-0f6a913edfa1/webhook"
fi
echo "Путь вебхука: $HOOK_PATH"

# 8. Set Telegram Webhook and Menu Button
echo "📲 [8/8] Регистрация вебхука в Telegram..."
SECRET_TOKEN="${WF_ID}_ca983051-1e1e-47a2-841b-a879fe4a7354"
WEBHOOK_TARGET="$TUNNEL_URL/webhook/$HOOK_PATH"

SET_RES=$(curl -s -F "url=$WEBHOOK_TARGET" \
     -F "secret_token=$SECRET_TOKEN" \
     "https://api.telegram.org/bot8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY/setWebhook")
echo "Ответ Telegram setWebhook: $SET_RES"

curl -s -X POST "https://api.telegram.org/bot8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY/setChatMenuButton" \
     -H "Content-Type: application/json" \
     -d "{\"menu_button\": {\"type\": \"web_app\", \"text\": \"✨ Каталог Tork\", \"web_app\": {\"url\": \"$TUNNEL_URL/webapp/\"}}}" > /dev/null

echo "🧪 Тестирование вебхука локально на сервере..."
TEST_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:8088/webhook/$HOOK_PATH" \
     -H "Content-Type: application/json" \
     -H "x-telegram-bot-api-secret-token: $SECRET_TOKEN" \
     -d '{"update_id":1,"message":{"message_id":999,"chat":{"id":5699064827,"type":"private"},"from":{"id":5699064827,"first_name":"Erlan"},"text":"/start"}}' || true)

echo "HTTP код ответа вебхука: $TEST_STATUS"

echo ""
echo "=================================================="
if [ "$TEST_STATUS" = "200" ]; then
    echo "🎉 УСПЕХ! Вебхук ответил 200 OK — бот полностью активен!"
else
    echo "⚠️ Вебхук вернул статус: $TEST_STATUS. Проверьте n8n логи: sudo docker compose logs n8n"
fi
echo "=================================================="
