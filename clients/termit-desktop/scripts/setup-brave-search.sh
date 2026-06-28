#!/bin/bash
# ==============================================================
# setup-brave-search.sh
# Установка и настройка Brave Search MCP для TermitPro
# ==============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DIR="$SCRIPT_DIR/mcp-servers/brave-search"

echo "=============================================="
echo "  TermitPro — Brave Search MCP Setup"
echo "=============================================="
echo ""

# Шаг 1: Установка зависимостей MCP-сервера
echo "📦 Устанавливаю зависимости MCP-сервера..."
cd "$MCP_DIR"

# Проверяем наличие npm
if ! command -v npm &> /dev/null; then
    echo "❌ npm не найден. Установите Node.js: https://nodejs.org"
    exit 1
fi

npm install

# Компилируем TypeScript
echo "🔧 Компилирую TypeScript..."
npx tsc

echo ""
echo "✅ MCP-сервер готов!"
echo ""
echo "=============================================="
echo "  ДАЛЕЕ:"
echo "=============================================="
echo ""
echo "1. Получите бесплатный Brave Search API ключ:"
echo "   https://api.search.brave.com"
echo ""
echo "2. Запустите TermitPro с API ключом:"
echo "   BRAVE_API_KEY=BS-xxxxxxx npm run dev"
echo ""
echo "   Или сохраните ключ в окружении (~/.zshrc):"
echo "   echo 'export BRAVE_API_KEY=BS-xxxxxxx' >> ~/.zshrc"
echo "   source ~/.zshrc"
echo "   npm run dev"
echo ""
echo "3. Нажмите 🔍 в левой панели TermitPro"
echo "   → откроется панель поиска"
echo ""
echo "=============================================="
