# Brave Search MCP — TermitPro

## Что это

Модуль поиска в интернете для TermitPro через Brave Search API.
Полностью локальный MCP-сервер, встроенный в приложение.

## Архитектура

```
termit-desktop/
├── mcp-servers/brave-search/     ← MCP-сервер (JSON-RPC через stdio)
│   ├── src/
│   │   ├── index.ts              ← Точка входа (парсинг аргументов)
│   │   ├── server.ts             ← MCP-сервер (tools/list, tools/call)
│   │   ├── brave-api.ts          ← HTTP-клиент Brave Search API
│   │   ├── cli.ts                ← Парсер CLI-аргументов
│   │   └── tools/
│   │       ├── webSearch.ts      ← brave_web_search
│   │       └── localSearch.ts    ← brave_local_search
│   ├── package.json
│   └── tsconfig.json
├── electron/
│   ├── main.ts                   ← IPC: brave:search, brave:start, brave:stop, brave:status
│   ├── preload.ts                ← API: braveSearch, braveSearchStatus, etc.
│   └── mcpClient.ts              ← MCP-клиент (spawn, JSON-RPC)
├── src/
│   ├── App.tsx                   ← Интеграция (кнопка 🔍 в rail)
│   └── SearchPanel.tsx          ← React-компонент (поле ввода, результаты)
└── scripts/
    └── setup-brave-search.sh     ← Скрипт установки
```

## Установка

```bash
# 1. Установить зависимости MCP-сервера и скомпилировать
bash scripts/setup-brave-search.sh

# 2. Получить API ключ на https://api.search.brave.com (бесплатно)

# 3. Запустить с ключом
BRAVE_API_KEY=BS-xxxxxxx npm run dev
```

## Использование

1. Нажать **🔍** в левой панели (rail) — откроется панель поиска
2. Ввести запрос → Enter
3. Результаты: заголовок, URL, описание, дата
4. Кнопки: **🌐 Открыть** (в браузере) / **📋 Вставить** (ссылку в чат)

## API ключ

Бесплатный план Brave Search API: **2000 запросов/месяц**.
Хватит для активного использования.

Получить: https://api.search.brave.com

## Инструменты MCP

| Инструмент | Описание |
|-----------|----------|
| `brave_web_search` | Поиск в интернете (актуальная информация, документация, новости) |
| `brave_local_search` | Поиск мест и бизнеса (рестораны, магазины, организации) |

## Протокол

MCP-сервер общается через **stdin/stdout** по **JSON-RPC 2.0**.
Независим от TermitPro — может использоваться любым AI-клиентом, поддерживающим MCP.
