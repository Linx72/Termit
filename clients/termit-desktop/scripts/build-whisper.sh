#!/bin/bash
# ────────────────────────────────────────────────────────────
# build-whisper.sh — сборка whisper.cpp для TermitPro
#
#   1. Клонирует whisper.cpp (если ещё не)
#   2. Компилирует с CoreML-ускорением (Apple Silicon)
#   3. Скачивает модель small (русский язык)
#
#   Использование:
#     cd clients/termit-desktop
#     bash scripts/build-whisper.sh
# ────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WHISPER_DIR="$PROJECT_DIR/whisper.cpp"
MODELS_DIR="$WHISPER_DIR/models"

MODEL="small"           # tiny | small | medium | large-v3
MODEL_URL_BASE="https://huggingface.co/ggerganov/whisper.cpp/resolve/main"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TermitPro Whisper Builder"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Project: $PROJECT_DIR"
echo "  Whisper: $WHISPER_DIR"
echo "  Model:   $MODEL"
echo ""

# ── Шаг 1: Клонируем whisper.cpp ────────────────────────

if [ ! -d "$WHISPER_DIR" ]; then
  echo "[1/3] Клонирую whisper.cpp…"
  git clone https://github.com/ggerganov/whisper.cpp.git "$WHISPER_DIR" --depth 1
else
  echo "[1/3] whisper.cpp уже существует. Обновляю…"
  cd "$WHISPER_DIR"
  git pull --ff-only origin master 2>/dev/null || true
fi

# ── Шаг 2: Компилируем с CoreML ─────────────────────────

echo "[2/3] Компилирую whisper.cpp с CoreML…"
cd "$WHISPER_DIR"

# Проверяем, есть ли cmake
if ! command -v cmake &>/dev/null; then
  echo "ОШИБКА: cmake не установлен. Выполните: brew install cmake"
  exit 1
fi

# Конфигурируем с CoreML
cmake -B build \
  -DWHISPER_COREML=1 \
  -DWHISPER_COREML_ALLOW_FALLBACK=1 \
  -DCMAKE_BUILD_TYPE=Release

# Собираем
cmake --build build -j --config Release

# Проверяем результат
WHISPER_BIN="$WHISPER_DIR/build/bin/whisper-cli"
if [ ! -f "$WHISPER_BIN" ]; then
  echo "ОШИБКА: whisper-cli не собран."
  echo "Проверьте вывод cmake выше."
  exit 1
fi

echo "  ✓ whisper-cli собран: $WHISPER_BIN"

# ── Шаг 3: Скачиваем модель ─────────────────────────────

echo "[3/3] Проверяю модель $MODEL…"
MODEL_FILE="$MODELS_DIR/ggml-${MODEL}.bin"

if [ -f "$MODEL_FILE" ]; then
  SIZE_MB=$(du -m "$MODEL_FILE" | cut -f1)
  echo "  ✓ Модель уже есть: $MODEL_FILE ($SIZE_MB MB)"
else
  mkdir -p "$MODELS_DIR"
  MODEL_URL="$MODEL_URL_BASE/ggml-${MODEL}.bin"
  echo "  Скачиваю $MODEL_URL …"
  curl -L -o "$MODEL_FILE" "$MODEL_URL" --progress-bar
  SIZE_MB=$(du -m "$MODEL_FILE" | cut -f1)
  echo "  ✓ Модель скачана: $MODEL_FILE ($SIZE_MB MB)"
fi

# ── Готово ───────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Готово!"
echo ""
echo "  whisper-cli: $WHISPER_BIN"
echo "  Модель:      $MODEL_FILE"
echo ""
echo "  Теперь запускайте TermitPro:"
echo "    cd $PROJECT_DIR && npm run dev"
echo ""
echo "  Горячая клавиша микрофона: Ctrl+Shift+Space"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
