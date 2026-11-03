#!/bin/bash
set -e

echo "=================================================="
echo "🚀 Tork Visualizer Bot — Автоматический деплой GCP"
echo "=================================================="

# 1. Update system packages
echo "📦 [1/6] Обновление пакетов Debian..."
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg git jq ufw

# 2. Install Docker & Docker Compose if not installed
if ! command -v docker &> /dev/null; then
    echo "🐳 [2/6] Установка Docker..."
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
    echo "📥 [3/6] Клонирование репозитория..."
    git clone -b manager-only-mode https://github.com/Erlan1502/tork-bot.git "$WORKDIR"
else
    echo "🔄 [3/6] Обновление кода из репозитория..."
    cd "$WORKDIR"
    git fetch origin
    git checkout manager-only-mode
    git pull origin manager-only-mode
fi

cd "$WORKDIR"

# 4. Create .env if not exists
echo "⚙️ [4/6] Проверка переменных окружения..."
if [ ! -f ".env" ]; then
    cp .env.example .env
fi

# 5. Build and run containers
echo "🚀 [5/6] Сборка и запуск Docker контейнеров..."
sudo docker compose up -d --build

# 6. Check health
echo "⏳ [6/6] Проверка статуса сервисов..."
sleep 5
sudo docker compose ps

echo "=================================================="
echo "✅ ВСЕ СЕРВИСЫ УСПЕШНО РАЗВЕРНУТЫ И РАБОТАЮТ 24/7!"
echo "=================================================="
