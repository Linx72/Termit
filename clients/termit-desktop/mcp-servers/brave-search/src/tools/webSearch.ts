/**
 * Инструмент: brave_web_search
 * Поиск в интернете через Brave Search API
 */

import { z } from 'zod';

/**
 * Схема параметров для brave_web_search
 * Используется для валидации JSON-RPC запросов
 */
export const WebSearchSchema = z.object({
  query: z
    .string()
    .min(1, 'Запрос не может быть пустым')
    .max(500, 'Запрос слишком длинный (макс. 500 символов)')
    .describe('Поисковый запрос (можно на любом языке)'),
  count: z
    .number()
    .int()
    .min(1)
    .max(20)
    .default(10)
    .describe('Количество результатов (1-20, по умолчанию 10)'),
});

export type WebSearchParams = z.infer<typeof WebSearchSchema>;

/**
 * Форматирует результаты поиска в читаемый текст
 */
export function formatWebSearchResults(
  results: Array<{ title: string; url: string; description: string; age?: string }>,
  query: string
): string {
  if (results.length === 0) {
    return `## 🔍 Результаты поиска по запросу "${query}"\n\n_Ничего не найдено. Попробуйте изменить запрос._`;
  }

  const lines: string[] = [
    `## 🔍 Результаты поиска по запросу "${query}"`,
    `_Найдено: ${results.length} результатов_\n`,
  ];

  for (let i = 0; i < results.length; i++) {
    const r = results[i];
    lines.push(`**${i + 1}. ${r.title}**`);
    lines.push(`   ${r.url}`);
    if (r.age) {
      lines.push(`   📅 ${r.age}`);
    }
    lines.push(`   ${r.description.slice(0, 200)}`);
    lines.push('');
  }

  return lines.join('\n');
}
