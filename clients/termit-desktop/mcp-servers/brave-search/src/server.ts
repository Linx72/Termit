/**
 * MCP Server: Brave Search
 * 
 * Реализует MCP (Model Context Protocol) сервер
 * с инструментами brave_web_search и brave_local_search
 * 
 * Протокол: JSON-RPC 2.0 через stdio
 * Библиотека: @modelcontextprotocol/sdk
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { BraveSearchAPI } from './brave-api.js';
import { WebSearchSchema, formatWebSearchResults } from './tools/webSearch.js';
import { LocalSearchSchema, formatLocalSearchResults } from './tools/localSearch.js';

/**
 * Создаёт и запускает MCP-сервер для Brave Search
 */
export function createBraveSearchMCPServer(apiKey: string) {
  const api = new BraveSearchAPI(apiKey);

  const server = new Server(
    {
      name: 'termit-brave-search-mcp',
      version: '1.0.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  /**
   * Обработчик: tools/list
   * Возвращает список доступных инструментов
   */
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [
        {
          name: 'brave_web_search',
          description: 'Поиск в интернете через Brave Search. ' +
            'Используйте для поиска актуальной информации, документации, новостей. ' +
            'Поддерживает русский и английский языки. ' +
            'Возвращает до 20 результатов с заголовками, URL и описаниями.\n\n' +
            'Параметры:\n' +
            '- query (строка, обязательный): поисковый запрос\n' +
            '- count (число, опционально): количество результатов (1-20, по умолчанию 10)',
          inputSchema: {
            type: 'object',
            properties: {
              query: {
                type: 'string',
                description: 'Поисковый запрос (можно на любом языке)',
              },
              count: {
                type: 'number',
                description: 'Количество результатов (1-20, по умолчанию 10)',
                default: 10,
              },
            },
            required: ['query'],
          },
        },
        {
          name: 'brave_local_search',
          description: 'Поиск мест, бизнеса, организаций через Brave Search. ' +
            'Используйте для поиска ресторанов, магазинов, компаний рядом. ' +
            'Возвращает название, адрес, телефон, рейтинг.\n\n' +
            'Параметры:\n' +
            '- query (строка, обязательный): что ищете (например: "кофейни в Москве")\n' +
            '- count (число, опционально): количество результатов (1-20, по умолчанию 5)',
          inputSchema: {
            type: 'object',
            properties: {
              query: {
                type: 'string',
                description: 'Что ищете (например: "рестораны рядом, аптеки, стоматология")',
              },
              count: {
                type: 'number',
                description: 'Количество результатов (1-20, по умолчанию 5)',
                default: 5,
              },
            },
            required: ['query'],
          },
        },
      ],
    };
  });

  /**
   * Обработчик: tools/call
   * Выполняет инструмент по имени
   */
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      switch (name) {
        case 'brave_web_search': {
          const params = WebSearchSchema.parse(args);
          const data = await api.webSearch(params.query, params.count);
          
          return {
            content: [
              {
                type: 'text',
                text: formatWebSearchResults(data.web?.results || [], params.query),
              },
            ],
          };
        }

        case 'brave_local_search': {
          const params = LocalSearchSchema.parse(args);
          const data = await api.localSearch(params.query, params.count);
          
          return {
            content: [
              {
                type: 'text',
                text: formatLocalSearchResults(data.locations?.results || [], params.query),
              },
            ],
          };
        }

        default:
          return {
            isError: true,
            content: [
              {
                type: 'text',
                text: `Неизвестный инструмент: "${name}". Доступны: brave_web_search, brave_local_search`,
              },
            ],
          };
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      
      return {
        isError: true,
        content: [
          {
            type: 'text',
            text: `❌ Ошибка: ${message}`,
          },
        ],
      };
    }
  });

  /**
   * Запуск сервера с stdio транспортом
   */
  return {
    async start(): Promise<void> {
      const transport = new StdioServerTransport();
      console.error('🧠 TermitPro Brave Search MCP Server запущен');
      console.error(`📊 Доступные инструменты: brave_web_search, brave_local_search`);
      
      await server.connect(transport);
      
      console.error('👋 MCP Server остановлен');
    },

    async stop(): Promise<void> {
      await server.close();
    },
  };
}
