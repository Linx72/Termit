#!/usr/bin/env node
/**
 * TermitPro Brave Search MCP Server
 * 
 * Запуск: BRAVE_API_KEY=BS-xxx node dist/index.js
 * или:    ter-mcp-brave-search --api-key BS-xxx
 * 
 * MCP протокол: JSON-RPC 2.0 через stdio
 * Инструменты:
 *   - brave_web_search    (поиск в интернете)
 *   - brave_local_search  (поиск мест/бизнеса)
 */

import { createBraveSearchMCPServer } from './server.js';
import { parseArgs } from './cli.js';

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  
  // Приоритет: аргумент > переменная окружения
  const apiKey = args.apiKey || process.env.BRAVE_API_KEY;
  
  if (!apiKey) {
    console.error('❌ Brave Search API ключ не найден.');
    console.error('');
    console.error('Получите бесплатный ключ: https://api.search.brave.com');
    console.error('');
    console.error('Запуск:');
    console.error('  BRAVE_API_KEY=BS-xxxxxx npx termit-brave-search');
    console.error('  или');
    console.error('  npx termit-brave-search --api-key BS-xxxxxx');
    process.exit(1);
  }

  const server = createBraveSearchMCPServer(apiKey);
  await server.start();
}

main().catch((err) => {
  console.error('❌ Фатальная ошибка:', err);
  process.exit(1);
});
