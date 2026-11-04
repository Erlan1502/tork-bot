#!/bin/bash
set -e

echo "=================================================="
echo "🔧 Полная диагностика и активация бота Tork..."
echo "=================================================="

WORKDIR="/home/$USER/tork-bot"
cd "$WORKDIR"

# 1. Update repo
echo "📥 [1/6] Обновление репозитория из ветки manager-only-mode..."
git fetch origin manager-only-mode
git reset --hard origin/manager-only-mode

# 2. Setup real .env with all AI and visualizer parameters
echo "⚙️ [2/6] Запись боевых переменных окружения..."
VLM_KEY="${1:-}"
if [ -z "$VLM_KEY" ]; then
    VLM_KEY=$(grep 'VLM_API_KEY=' .env 2>/dev/null | cut -d '=' -f2- || true)
fi

cat << EOF > .env
TELEGRAM_BOT_TOKEN=8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY
ALLOWED_TELEGRAM_IDS=5699064827,7390702902,1248663402
MANAGER_CHAT_ID=-100200300400
VLM_API_KEY=$VLM_KEY
VLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
VLM_MODEL_NAME=gemini-4.0-argon
IMAGE_EDIT_MODEL=gemini-3.1-flash-image
IMAGE_EDIT_API_KEY=$VLM_KEY
IMAGE_EDIT_API_URL=https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image:generateContent
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
MAX_RENDERS_PER_USER_DAY=10
EOF

# 3. Restore n8n database dump (includes credentials, users, workflow and webhooks)
echo "💾 [3/6] Восстановление дампа базы данных n8n в PostgreSQL..."
sudo docker exec -i tork_postgres psql -U tork_admin -d tork_bot_db < n8n_dump.sql

# 4. Get current Tunnel URL
echo "🌐 [4/6] Определение адреса туннеля Cloudflare..."
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

# 5. Apply updated .env and recreate containers
echo "🔄 [5/6] Применение переменных и перезапуск сервисов (docker compose up -d)..."
sudo docker compose up -d --remove-orphans

echo "⏳ Ожидание полной готовности n8n..."
for i in {1..30}; do
    CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5679/" || true)
    if [ "$CODE" = "200" ] || [ "$CODE" = "401" ]; then
        echo "✅ n8n готов (код $CODE, попытка $i)!"
        break
    fi
    sleep 2
done

# Publish workflow in n8n and wait for router activation
echo "📢 Публикация и активация рабочего процесса n8n..."
sudo docker exec -u node tork_n8n n8n publish:workflow --id=sHnoGT842oAJacFu || true
sudo docker restart tork_n8n

echo "⏳ Ожидание перезапуска n8n после публикации..."
for i in {1..30}; do
    CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5679/" || true)
    if [ "$CODE" = "200" ] || [ "$CODE" = "401" ]; then
        echo "✅ n8n снова онлайн (попытка $i)!"
        break
    fi
    sleep 2
done

# 6. Set Telegram Webhook and Menu Button
echo "📲 [6/6] Регистрация вебхука в Telegram..."
SECRET_TOKEN="sHnoGT842oAJacFu_ca983051-1e1e-47a2-841b-a879fe4a7354"
WEBHOOK_TARGET="$TUNNEL_URL/webhook/6203b22d-7f6e-4731-b245-0f6a913edfa1/webhook"

SET_RES=$(curl -s -F "url=$WEBHOOK_TARGET" \
     -F "secret_token=$SECRET_TOKEN" \
     "https://api.telegram.org/bot8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY/setWebhook")
echo "Ответ Telegram setWebhook: $SET_RES"

curl -s -X POST "https://api.telegram.org/bot8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY/setChatMenuButton" \
     -H "Content-Type: application/json" \
     -d "{\"menu_button\": {\"type\": \"web_app\", \"text\": \"✨ Каталог Tork\", \"web_app\": {\"url\": \"$TUNNEL_URL/webapp/\"}}}" > /dev/null

echo "🧪 Тестирование вебхука на сервере..."
TEST_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:8088/webhook/6203b22d-7f6e-4731-b245-0f6a913edfa1/webhook" \
     -H "Content-Type: application/json" \
     -H "x-telegram-bot-api-secret-token: $SECRET_TOKEN" \
     -d '{"update_id":1,"message":{"message_id":999,"chat":{"id":5699064827,"type":"private"},"from":{"id":5699064827,"first_name":"Erlan"},"text":"/start"}}' || true)

echo "HTTP код ответа вебхука: $TEST_STATUS"

echo ""
echo "=================================================="
if [ "$TEST_STATUS" = "200" ]; then
    echo "🎉 УСПЕХ! Вебхук ответил 200 OK — бот полностью активен!"
else
    echo "⚠️ Вебхук вернул статус: $TEST_STATUS. Логи n8n:"
    sudo docker logs tork_n8n --tail 25
fi
echo "=================================================="
