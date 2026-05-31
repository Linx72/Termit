# GitHub — одноразовая настройка

Репозиторий: **https://github.com/Linx72/Termit**  
Remote уже: `git@github.com:Linx72/Termit.git`

## 1. SSH-ключ (рекомендуется)

```bash
./scripts/setup_github_ssh.sh
./scripts/add_github_ssh_key.sh
```

Скрипт `add_github_ssh_key.sh` копирует ключ в буфер и открывает страницу добавления.

**Полностью без браузера** (нужен [Personal Access Token](https://github.com/settings/tokens) с правом `admin:public_key`):

```bash
export TERMIT_GITHUB_TOKEN='ghp_...'
./scripts/add_github_ssh_key.sh
```

Или вручную:

```bash
cat ~/.ssh/id_ed25519.pub
```

Вставьте ключ: https://github.com/settings/keys

Проверка:

```bash
ssh -T git@github.com
```

## 2. Создать пустой репозиторий (если 404)

https://github.com/new → имя **Termit**, без README.

## 3. Первый push

```bash
cd /path/to/Termit
./scripts/first_push.sh
```

Или вручную:

```bash
git push -u origin main
git push origin v0.3.2
```

## 4. Ежедневно на разных ПК

```bash
./scripts/sync_start.sh
# работа...
./scripts/sync_finish.sh "описание изменений"
```

См. [SYNC_WORKFLOW.md](SYNC_WORKFLOW.md).

## HTTPS вместо SSH

```bash
git remote set-url origin https://github.com/Linx72/Termit.git
git push -u origin main
# логин: GitHub username, пароль: Personal Access Token
```
