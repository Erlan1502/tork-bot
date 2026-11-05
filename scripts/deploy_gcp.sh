#!/bin/bash
set -e

echo "=================================================="
echo "🚀 Tork Visualizer Bot — Автоматический деплой GCP"
echo "=================================================="

# 1. Update system packages
echo "📦 [1/7] Обновление пакетов Debian..."
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg git jq ufw

# 2. Install Docker & Docker Compose if not installed
if ! command -v docker &> /dev/null; then
    echo "🐳 [2/7] Установка Docker..."
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    
    echo \
      "deb [arch=\"$(dpkg --print-architecture)\" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
      \"$(. /etc/os-release && echo \"$VERSION_CODENAME\")\" stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker $USER
    echo "Docker успешно установлен!"
else
    echo "Docker уже установлен."
fi

# 3. Pull latest code
WORKDIR="/home/$USER/tork-bot"
if [ ! -d "$WORKDIR" ]; then
    echo "📥 [3/7] Клонирование репозитория..."
    git clone -b manager-only-mode https://github.com/Erlan1502/tork-bot.git "$WORKDIR"
else
    echo "🔄 [3/7] Обновление кода из репозитория..."
    cd "$WORKDIR"
    git fetch origin
    git checkout manager-only-mode
    git pull origin manager-only-mode
fi

cd "$WORKDIR"

# 4. Generate Production .env
echo "⚙️ [4/7] Настройка производственного окружения (.env)..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    # Update manager IDs if specified
    sed -i 's/^ALLOWED_TELEGRAM_IDS=.*/ALLOWED_TELEGRAM_IDS=5699064827,7390702902,1248663402,385661842/' .env
fi

# 5. Build and run main containers
echo "🚀 [5/7] Сборка и запуск Docker контейнеров..."
sudo docker compose up -d --build

# 6. Launch Persistent Cloudflare Tunnel
echo "🌐 [6/7] Запуск Cloudflare HTTPS Tunnel (24/7)..."
sudo docker rm -f cloudflared 2>/dev/null || true
sudo docker run -d --name cloudflared --restart unless-stopped --network host cloudflare/cloudflared:latest tunnel --url http://localhost:8088

# Wait for tunnel URL
echo "Ожидание выделения HTTPS адреса..."
TUNNEL_URL=""
for i in {1..30}; do
    TUNNEL_URL=$(sudo docker logs cloudflared 2>&1 | grep -o 'https://[-a-zA-Z0-9.]*\.trycloudflare\.com' | head -n 1 || true)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
    sleep 2
done

if [ -z "$TUNNEL_URL" ]; then
    echo "⚠️ Не удалось автоматически прочитать URL туннеля. Проверьте: sudo docker logs cloudflared"
else
    echo "✅ Постоянный HTTPS адрес: $TUNNEL_URL"
    
    # Update WEBHOOK_URL in .env
    echo "WEBHOOK_URL=$TUNNEL_URL" >> .env
    
    # 7. Register Telegram Webhook
    echo "📲 [7/7] Привязка вебхука в Telegram..."
    SECRET_TOKEN="4pE0xH1m8g94FvI7_Telegram_Trigger"
    curl -s -F "url=$TUNNEL_URL/webhook/tork-bot-webhook" \
         -F "secret_token=$SECRET_TOKEN" \
         "https://api.telegram.org/bot8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY/setWebhook" > /dev/null
    
    # Set Menu Button
    curl -s -X POST "https://api.telegram.org/bot8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY/setChatMenuButton" \
         -H "Content-Type: application/json" \
         -d "{\"menu_button\": {\"type\": \"web_app\", \"text\": \"✨ Каталог Tork\", \"web_app\": {\"url\": \"$TUNNEL_URL/webapp/\"}}}" > /dev/null
fi

echo ""
echo "=================================================="
echo "🎉 БОТ УСПЕШНО РАЗВЕРНУТ И РАБОТАЕТ В GOOGLE CLOUD!"
echo "👥 Авторизованные менеджеры: 5699064827, 7390702902, 1248663402, 385661842"
if [ -n "$TUNNEL_URL" ]; then
    echo "🌐 Веб-каталог: $TUNNEL_URL/webapp/"
fi
echo "=================================================="
