/**
 * Инструмент: brave_local_search
 * Поиск мест, бизнеса, организаций рядом
 */

import { z } from 'zod';

/**
 * Схема параметров для brave_local_search
 */
export const LocalSearchSchema = z.object({
  query: z
    .string()
    .min(1, 'Запрос не может быть пустым')
    .max(500, 'Запрос слишком длинный')
    .describe('Поиск мест: рестораны, магазины, организации...'),
  count: z
    .number()
    .int()
    .min(1)
    .max(20)
    .default(5)
    .describe('Количество результатов (1-20, по умолчанию 5)'),
});

export type LocalSearchParams = z.infer<typeof LocalSearchSchema>;

/**
 * Форматирует результаты локального поиска
 */
export function formatLocalSearchResults(
  results: Array<{
    title: string;
    url: string;
    description: string;
    phone?: string;
    rating?: number;
    reviews?: number;
    address?: string;
  }>,
  query: string
): string {
  if (results.length === 0) {
    return `## 📍 Поиск мест по запросу "${query}"\n\n_Ничего не найдено. Попробуйте изменить запрос._`;
  }

  const lines: string[] = [
    `## 📍 Места по запросу "${query}"`,
    `_Найдено: ${results.length} мест_\n`,
  ];

  for (let i = 0; i < results.length; i++) {
    const r = results[i];
    lines.push(`**${i + 1}. ${r.title}**`);
    if (r.rating) {
      const stars = '⭐'.repeat(Math.round(r.rating));
      lines.push(`   ${stars} ${r.rating.toFixed(1)} (${r.reviews ?? 0} отзывов)`);
    }
    if (r.address) lines.push(`   📍 ${r.address}`);
    if (r.phone) lines.push(`   📞 ${r.phone}`);
    lines.push(`   ${r.url}`);
    lines.push(`   ${r.description.slice(0, 200)}`);
    lines.push('');
  }

  return lines.join('\n');
}
