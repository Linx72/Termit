# 🎤 Голосовой ввод в TermitPro

## Быстрый старт (2 команды)

```bash
cd /Users/amoros/Projects/Termit/clients/termit-desktop

# Шаг 1: Собрать whisper.cpp + скачать модель (466 MB)
chmod +x scripts/build-whisper.sh && bash scripts/build-whisper.sh

# Шаг 2: Установить зависимости и запустить
npm install && npm run dev
```

## Как пользоваться

| Действие | Результат |
|----------|-----------|
| Нажать 🎤 в тулбаре ввода | Начинается запись |
| Говорить | Текст появляется в реальном времени |
| Нажать 🎤 ещё раз (или Ctrl+Shift+Space) | Стоп, текст вставляется в поле ввода |
| Навести на 🎤 | Показать состояние (готов/запись/модель загружается) |

## Системные требования

- macOS 12+ (Monterey или новее)
- Apple Silicon (M1/M2/M3) — CoreML ускорение
- 500 MB свободного места (модель 466 MB)
- Микрофон (встроенный или внешний)

## Приватность

✅ Всё локально — аудио НЕ покидает устройство  
✅ Бесплатно — open source  
✅ Не требует интернета (после скачивания модели)

## Диагностика

Если кнопка микрофона не появляется или не работает:
1. Откройте DevTools: Cmd+Option+I
2. Смотрите ошибки в console
3. Проверьте разрешения микрофона:
   Системные настройки → Конфиденциальность → Микрофон → TermitPro

## Структура файлов

```
electron/
  whisperManager.ts   — Управление whisper.cpp (281 строка)
  main.ts             — IPC-обработчики (строки 198-227)
  preload.ts          — API для renderer (строки 29-38, 66-76)
shared/
  ipc.ts              — Типы WhisperModelStatus, WhisperStreamResult
src/
  MicrophoneButton.tsx — React-компонент с VU-метром (403 строки)
  App.tsx             — Интеграция (строка 3657)
  cursorShell.css     — Стили кнопки (строки 452-470)
scripts/
  build-whisper.sh    — Скрипт сборки (61 строка)
WHISPER_SETUP.md      — Этот файл
```

## Изменённые файлы (8)

- `electron/whisperManager.ts` — **НОВЫЙ**
- `electron/main.ts` — изменён (добавлены 5 IPC-обработчиков)
- `electron/preload.ts` — изменён (добавлены 5 API-методов)
- `shared/ipc.ts` — изменён (добавлены типы)
- `src/MicrophoneButton.tsx` — **НОВЫЙ**
- `src/App.tsx` — изменён (импорт + интеграция кнопки)
- `src/cursorShell.css` — изменён (стили микрофона)
- `scripts/build-whisper.sh` — **НОВЫЙ**
