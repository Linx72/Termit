/**
 * SearchPanel — панель поиска в интернете через Brave Search API
 * 
 * Использует MCP-сервер brave-search, запущенный в main процессе.
 * Взаимодействует через window.termitDesktop.braveSearch().
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';

interface SearchResult {
  title: string;
  url: string;
  description: string;
  age?: string;
}

interface SearchPanelProps {
  /** Вызывается, когда пользователь хочет вставить ссылку в чат */
  onInsertUrl?: (url: string, title: string) => void;
  /** Вызывается, когда пользователь хочет открыть URL в браузере */
  onOpenUrl?: (url: string) => void;
}

export function SearchPanel({ onInsertUrl, onOpenUrl }: SearchPanelProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'searching' | 'results' | 'error'>('idle');
  const [total, setTotal] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Фокус на поле ввода при монтировании
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  /**
   * Выполнить поиск
   */
  const handleSearch = useCallback(async () => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;

    setLoading(true);
    setError(null);
    setStatus('searching');

    try {
      // Проверяем, не использует ли API сам Brave Search
      const response = await window.termitDesktop.braveSearch(trimmedQuery, 10);
      
      if (response.error) {
        setError(response.error);
        setStatus('error');
        setResults([]);
        setTotal(0);
      } else {
        setResults(response.results);
        setTotal(response.total);
        setStatus('results');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setError(message);
      setStatus('error');
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [query]);

  /**
   * Обработка нажатия Enter в поле поиска
   */
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !loading) {
      handleSearch();
    }
  }, [handleSearch, loading]);

  /**
   * Вставить URL в чат
   */
  const handleInsertUrl = useCallback((url: string, title: string) => {
    onInsertUrl?.(url, title);
  }, [onInsertUrl]);

  /**
   * Открыть URL во внешнем браузере
   */
  const handleOpenUrl = useCallback((url: string) => {
    onOpenUrl?.(url);
  }, [onOpenUrl]);

  /**
   * Очистить результаты
   */
  const handleClear = useCallback(() => {
    setQuery('');
    setResults([]);
    setError(null);
    setStatus('idle');
    setTotal(0);
    inputRef.current?.focus();
  }, []);

  return (
    <div className="search-panel">
      {/* Шапка */}
      <div className="search-panel-header">
        <h3 className="search-panel-title">
          <span className="search-icon">🔍</span>
          Поиск в интернете
        </h3>
        <span className="search-powered">
          Brave Search
        </span>
      </div>

      {/* Поле ввода */}
      <div className="search-input-wrapper">
        <input
          ref={inputRef}
          type="text"
          className="search-input"
          placeholder="Введите поисковый запрос..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <div className="search-input-actions">
          {query && (
            <button
              className="search-btn search-btn-clear"
              onClick={handleClear}
              title="Очистить"
              disabled={loading}
            >
              ✕
            </button>
          )}
          <button
            className="search-btn search-btn-submit"
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            title="Поиск"
          >
            {loading ? '⏳' : '🔍'}
          </button>
        </div>
      </div>

      {/* Статус загрузки */}
      {loading && (
        <div className="search-status">
          <div className="search-spinner"></div>
          <span>Ищу: "{query}"...</span>
        </div>
      )}

      {/* Ошибка */}
      {error && status === 'error' && (
        <div className="search-error">
          <span className="search-error-icon">⚠️</span>
          <div className="search-error-body">
            <strong>Ошибка поиска</strong>
            <p>{error}</p>
            {error.includes('BRAVE_API_KEY') && (
              <div className="search-error-actions">
                <a
                  href="https://api.search.brave.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="search-link"
                >
                  Получить ключ Brave Search API →
                </a>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Результаты */}
      {results.length > 0 && status === 'results' && (
        <div className="search-results">
          <div className="search-results-header">
            <span>Найдено: {total} результатов</span>
            <span className="search-results-query">"{query}"</span>
          </div>
          <div className="search-results-list">
            {results.map((result, index) => (
              <div key={index} className="search-result-item">
                <div className="search-result-number">{index + 1}</div>
                <div className="search-result-content">
                  <a
                    className="search-result-title"
                    href={result.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => {
                      e.preventDefault();
                      handleOpenUrl(result.url);
                    }}
                  >
                    {result.title}
                  </a>
                  <div className="search-result-url">
                    <span className="search-result-domain">
                      {new URL(result.url).hostname}
                    </span>
                    {result.age && (
                      <span className="search-result-age"> · {result.age}</span>
                    )}
                  </div>
                  <p className="search-result-description">{result.description}</p>
                  <div className="search-result-actions">
                    <button
                      className="search-link-btn"
                      onClick={() => handleOpenUrl(result.url)}
                      title="Открыть в браузере"
                    >
                      🌐 Открыть
                    </button>
                    <button
                      className="search-link-btn"
                      onClick={() => handleInsertUrl(result.url, result.title)}
                      title="Вставить ссылку в чат"
                    >
                      📋 Вставить
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Пустое состояние */}
      {status === 'idle' && !loading && !error && (
        <div className="search-empty">
          <div className="search-empty-icon">🔍</div>
          <p className="search-empty-text">
            Найдите информацию в интернете
          </p>
          <p className="search-empty-hint">
            Введите запрос и нажмите Enter. Используется Brave Search API.
          </p>
        </div>
      )}
    </div>
  );
}
