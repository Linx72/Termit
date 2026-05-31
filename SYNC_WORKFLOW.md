# Синхронизация Termit между компьютерами

GitHub — единственный источник правды. Локальные изменения на каждой машине должны регулярно попадать в `origin/main`.

**Репозиторий:** https://github.com/orosam/Termit

---

## Первый запуск на новом компьютере

### 1. Доступ к GitHub

Нужен один из вариантов:

- **SSH** (рекомендуется): ключ в GitHub → Settings → SSH and GPG keys  
  Проверка: `ssh -T git@github.com`
- **HTTPS + PAT**: Personal Access Token с правом `repo`  
  При первом `git push` Git запросит логин и токен вместо пароля.

### 2. Клонирование

```bash
git clone git@github.com:orosam/Termit.git
cd Termit
```

HTTPS-вариант:

```bash
git clone https://github.com/orosam/Termit.git
cd Termit
```

Или запустите автоматическую настройку из уже клонированной копии:

```bash
./scripts/setup_new_machine.sh
```

### 3. Окружение Python

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Локальный `.env`

```bash
cp .env.example .env
# Отредактируйте .env под эту машину (модели, URL провайдеров, ключи API).
```

`.env` **никогда не коммитьте** — он в `.gitignore`.

### 5. Первый push с машины, где уже есть коммиты

Если репозиторий на GitHub ещё пустой или отстаёт (после настройки SSH или PAT):

```bash
./scripts/first_push.sh
```

Или вручную:

```bash
git push -u origin main
git push origin v0.2.0   # тег релиза, если есть локально
```

---

## Ежедневная рутина

| Когда | Что делать |
|-------|------------|
| **Начало работы** | `./scripts/sync_start.sh` |
| **Конец работы** | `./scripts/sync_finish.sh "краткое описание изменений"` |

### Вручную (то же самое)

```bash
# Утро / начало сессии
git fetch origin
git pull --rebase origin main
git status

# Вечер / после задачи
git add -A
git commit -m "описание изменений"
git push origin main
```

### Однострочник на каждый день

**Утром:** `./scripts/sync_start.sh` — **вечером:** `./scripts/sync_finish.sh "что сделали"`.

---

## Что НЕ коммитить

| Файл / паттерн | Почему |
|----------------|--------|
| `.env` | Секреты и локальные настройки |
| `*.db`, `*.db-journal` | SQLite (память, задачи, agent runs) |
| `.venv/` | Виртуальное окружение |
| `data/*` (кроме seed JSON) | Runtime-артефакты агентов |
| `__pycache__/`, `*.pyc` | Кэш Python |

Проверка перед коммитом: `git status` — в списке не должно быть `.env` или `.db`.

---

## Конфликты на двух машинах

1. На машине A вы уже запушили изменения.
2. На машине B забыли сделать `pull` и тоже что-то закоммитили.

**Решение на машине B:**

```bash
git fetch origin
git pull --rebase origin main
```

- Если конфликт в файлах — Git остановится; откройте файлы с маркерами `<<<<<<<`, исправьте, затем:

```bash
git add <исправленные-файлы>
git rebase --continue
```

- Если rebase слишком запутался:

```bash
git rebase --abort
git pull origin main    # merge-коммит — проще, но история менее ровная
```

**Правило:** всегда `pull --rebase` **до** начала работы — конфликтов будет меньше.

---

## Опционально: ветки для фич

Для крупных задач удобнее отдельная ветка:

```bash
git pull --rebase origin main
git checkout -b feature/my-task
# ... работа ...
git push -u origin feature/my-task
# PR на GitHub → merge в main
```

На другой машине:

```bash
git fetch origin
git checkout feature/my-task
git pull --rebase origin feature/my-task
```

После merge PR на GitHub:

```bash
git checkout main
git pull --rebase origin main
git branch -d feature/my-task
```

---

## Полезные алиасы (локально, без изменения global config)

Добавьте в `.git/config` **только в этом репозитории** (файл `.git/config`, не `--global`):

```ini
[alias]
  up = pull --rebase origin main
  save = !f(){ git add -A && git commit -m \"${1:-wip}\" && git push origin main; }; f
```

Использование: `git up`, `git save "сообщение"`.

Подробнее: [.github/SYNC.md](.github/SYNC.md).

---

## Если push не проходит

| Ошибка | Действие |
|--------|----------|
| `Permission denied (publickey)` | Настройте SSH-ключ или переключите remote на HTTPS |
| `could not read Username` | Используйте PAT для HTTPS |
| `rejected (non-fast-forward)` | Сначала `git pull --rebase origin main`, потом снова push |
| `Repository not found` | Создайте repo `orosam/Termit` на GitHub или проверьте права доступа |

Переключение remote на HTTPS (без global config):

```bash
git remote set-url origin https://github.com/orosam/Termit.git
```

---

## Версии и теги

Релиз **v0.2.0** помечен тегом. После клонирования все теги:

```bash
git fetch --tags
git tag -l
```

Новый релиз (когда готовы):

```bash
git tag -a v0.2.1 -m "Release 0.2.1"
git push origin main
git push origin v0.2.1
```
