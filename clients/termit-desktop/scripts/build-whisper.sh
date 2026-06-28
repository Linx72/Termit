#!/usr/bin/env bash
#
# Сборка whisper.cpp с CoreML-ускорением для Apple Silicon (M1/M2/M3).
# Запускать из clients/termit-desktop/.
#
# Требования: cmake, Xcode Command Line Tools.
#
set -euo pipefail

WHISPER_REPO="https://github.com/ggerganov/whisper.cpp.git"
WHISPER_DIR="$(cd "$(dirname "$0")/.." && pwd)/whisper.cpp"

echo "==> Проверяю зависимости…"
command -v cmake >/dev/null 2>&1 || { echo "ОШИБКА: cmake не установлен. Выполни: brew install cmake"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "ОШИБКА: git не установлен."; exit 1; }

# Клонировать, если ещё нет
if [ ! -d "$WHISPER_DIR" ]; then
  echo "==> Клонирую whisper.cpp…"
  git clone "$WHISPER_REPO" "$WHISPER_DIR" --depth 1
else
  echo "==> whisper.cpp уже есть в $WHISPER_DIR"
fi

cd "$WHISPER_DIR"

# Скачать модель small для CoreML (нужна для конвертации)
MODEL_DIR="$WHISPER_DIR/models"
if [ ! -f "$MODEL_DIR/ggml-small.bin" ]; then
  echo "==> Скачиваю модель small (466 MB)…"
  mkdir -p "$MODEL_DIR"
  bash "$WHISPER_DIR/models/download-ggml-model.sh" small
else
  echo "==> Модель small уже скачана."
fi

echo "==> CMake configure (CoreML ON)…"
cmake -B build \
  -DWHISPER_COREML=1 \
  -DWHISPER_COREML_ALLOW_FALLBACK=1 \
  -DCMAKE_BUILD_TYPE=Release

echo "==> Сборка…"
cmake --build build -j$(sysctl -n hw.logicalcpu) --config Release

echo "==> Проверяю бинарник…"
BIN="$WHISPER_DIR/build/bin/whisper-cli"
if [ -f "$BIN" ]; then
  echo "✅ whisper-cli собран: $BIN"
  file "$BIN"
else
  echo "❌ Ошибка: бинарник не найден. Проверь вывод cmake выше."
  exit 1
fi

echo ""
echo "==> Готово! whisper.cpp собран с CoreML."
echo "    Бинарник: $BIN"
echo "    Модель:   $MODEL_DIR/ggml-small.bin"
