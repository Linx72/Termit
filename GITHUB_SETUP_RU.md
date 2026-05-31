# GitHub — одноразовая настройка

Репозиторий: **https://github.com/orosam/Termit**  
Remote уже: `git@github.com:orosam/Termit.git`

## 1. SSH-ключ (рекомендуется)

```bash
ssh-keygen -t ed25519 -C "your@email" -f ~/.ssh/id_ed25519 -N ""
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
git remote set-url origin https://github.com/orosam/Termit.git
git push -u origin main
# логин: GitHub username, пароль: Personal Access Token
```
