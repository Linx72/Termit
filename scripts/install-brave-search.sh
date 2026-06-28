#!/usr/bin/env bash
# ============================================================================
# BraveSearch MCP Server — установка и настройка
# ============================================================================
set -euo pipefail

TERMIT_DESKTOP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../clients/termit-desktop" && pwd)"
ENV_FILE="$HOME/.termit/.env"
BRAVE_API_KEY="${BRAVE_API_KEY:-}"

echo "======================================================"
echo "  BraveSearch MCP Server — установка в TermitPro"
echo "======================================================"
echo ""

# ── 1. Проверка Node.js ────────────────────────────────────────
if ! command -v node &> /dev/null; then
    echo "❌ Node.js не найден. Установите: brew install node"
    exit 1
fi
echo "✅ Node.js: $(node -v)"

# ── 2. Установка @brave/brave-search-mcp-server ────────────────
echo ""
echo "📦 Устанавливаю @brave/brave-search-mcp-server..."
cd "$TERMIT_DESKTOP_DIR"
npm install --save-dev @brave/brave-search-mcp-server 2>&1 | tail -1
echo "✅ Пакет установлен"

# ── 3. API-ключ ─────────────────────────────────────────────────
mkdir -p "$HOME/.termit"

if [ -z "$BRAVE_API_KEY" ]; then
    echo ""
    echo "🔑 Нужен бесплатный BRAVE_API_KEY (2000 запросов/мес)."
    echo ""
    echo "  Как получить:"
    echo "  1. Открой: https://brave.com/search/api/"
    echo "  2. Нажми 'Get Started for Free'"
    echo "  3. Зарегистрируйся → скопируй API-ключ"
    echo ""
    read -r -p "Вставь BRAVE_API_KEY сюда: " BRAVE_API_KEY
fi

if [ -z "$BRAVE_API_KEY" ]; then
    echo "❌ API-ключ не указан. Пропускаю."
    exit 0
fi

# Сохраняем ключ
if grep -q "^BRAVE_API_KEY=" "$ENV_FILE" 2>/dev/null; then
    sed -i '' "s/^BRAVE_API_KEY=.*/BRAVE_API_KEY=$BRAVE_API_KEY/" "$ENV_FILE"
else
    echo "BRAVE_API_KEY=$BRAVE_API_KEY" >> "$ENV_FILE"
fi
echo "✅ API-ключ сохранён в $ENV_FILE"

# ── 4. Проверка запуска ─────────────────────────────────────────
echo ""
echo "🧪 Проверяю запуск MCP-сервера..."
MCP_BIN="$TERMIT_DESKTOP_DIR/node_modules/.bin/brave-search-mcp-server"

if [ ! -f "$MCP_BIN" ]; then
    echo "❌ Бинарник не найден: $MCP_BIN"
    echo "   Попробуй: cd $TERMIT_DESKTOP_DIR && npx @brave/brave-search-mcp-server --help"
    exit 1
fi

# Проверка: список инструментов через STDIO
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | \
    timeout 10 env BRAVE_API_KEY="$BRAVE_API_KEY" node "$MCP_BIN" 2>/dev/null || true

echo ""
echo "======================================================"
echo "  ✅ BraveSearch MCP готов к работе!"
echo "======================================================"
echo ""
echo "  Инструменты:"
echo "  • brave_web_search     — поиск в интернете"
echo "  • brave_local_search   — локальный поиск (бизнес/места)"
echo "  • brave_image_search   — поиск изображений"
echo "  • brave_video_search   — поиск видео"
echo "  • brave_news_search    — поиск новостей"
echo "  • brave_place_search   — поиск мест"
echo ""
echo "  Бесплатно: 2000 запросов/мес"
echo ""
