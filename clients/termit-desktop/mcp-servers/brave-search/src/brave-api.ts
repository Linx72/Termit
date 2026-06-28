/**
 * HTTP-клиент для Brave Search API
 * Документация: https://api.search.brave.com/app/documentation
 * Бесплатный план: 2000 запросов/месяц
 */

export interface BraveWebSearchResult {
  title: string;
  url: string;
  description: string;
  age?: string;
  source?: string;
}

export interface BraveWebSearchResponse {
  web: {
    results: BraveWebSearchResult[];
  };
  query: {
    original: string;
    modified?: string;
  };
}

export interface BraveLocalSearchResult {
  title: string;
  url: string;
  description: string;
  phone?: string;
  rating?: number;
  reviews?: number;
  address?: string;
  coordinates?: {
    latitude: number;
    longitude: number;
  };
}

export interface BraveLocalSearchResponse {
  locations: {
    results: BraveLocalSearchResult[];
  };
}

export class BraveSearchAPI {
  private readonly apiKey: string;
  private readonly baseUrl = 'https://api.search.brave.com/res/v1';
  private requestCount = 0;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  /**
   * Поиск в интернете
   */
  async webSearch(query: string, count: number = 10): Promise<BraveWebSearchResponse> {
    this.requestCount++;
    
    const url = new URL(`${this.baseUrl}/web/search`);
    url.searchParams.set('q', query);
    url.searchParams.set('count', String(Math.min(count, 20))); // Brave лимит 20
    url.searchParams.set('search_lang', 'ru');
    url.searchParams.set('spellcheck', '1');
    url.searchParams.set('safesearch', 'moderate');

    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Accept-Language': 'ru-RU, ru; q=0.9, en; q=0.7',
        'X-Subscription-Token': this.apiKey,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      
      if (response.status === 401) {
        throw new Error('Неверный Brave Search API ключ. Проверьте ключ в настройках.');
      } else if (response.status === 429) {
        throw new Error('Превышен лимит запросов Brave Search API (2000/месяц на бесплатном плане).');
      } else if (response.status === 402) {
        throw new Error('Исчерпан лимит бесплатных запросов. Обновите план на https://api.search.brave.com');
      }
      
      throw new Error(`Brave Search API ошибка ${response.status}: ${errorText}`);
    }

    const data = await response.json() as BraveWebSearchResponse;
    return data;
  }

  /**
   * Поиск мест/бизнеса (локальный поиск)
   */
  async localSearch(query: string, count: number = 5): Promise<BraveLocalSearchResponse> {
    this.requestCount++;

    const url = new URL(`${this.baseUrl}/search/local`);
    url.searchParams.set('q', query);
    url.searchParams.set('count', String(Math.min(count, 20)));

    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Accept-Language': 'ru-RU, ru; q=0.9, en; q=0.7',
        'X-Subscription-Token': this.apiKey,
      },
    });

    if (!response.ok) {
      throw new Error(`Brave Local Search API ошибка ${response.status}`);
    }

    const data = await response.json() as BraveLocalSearchResponse;
    return data;
  }

  /**
   * Количество выполненных запросов
   */
  getRequestCount(): number {
    return this.requestCount;
  }
}
