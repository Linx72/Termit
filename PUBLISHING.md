# Publishing Termit

## Prerequisites

- GitHub account and `gh` CLI authenticated (`gh auth login`)
- Clean test run: `python -m unittest discover -s tests -v`
- Version bumped in `VERSION` and `CHANGELOG.md`

## First-time remote

```bash
cd /path/to/Termit
git remote add origin git@github.com:<org>/termit.git
git push -u origin main
```

Replace `<org>/termit` with your repository slug.

## Release checklist

1. Update `VERSION` (semver, no `v` prefix in file).
2. Add a `CHANGELOG.md` section for the release.
3. Commit and push `main`.
4. Tag and push:

```bash
git tag v0.2.0
git push origin v0.2.0
```

5. GitHub Actions workflow `.github/workflows/release.yml` creates the release artifact notes.
6. Optional manual release body:

```bash
gh release create v0.2.0 --title "Termit 0.2.0" --notes-file CHANGELOG.md
```

## Docker publish (optional)

```bash
docker build -t ghcr.io/<org>/termit:0.2.0 .
docker push ghcr.io/<org>/termit:0.2.0
```

Document image coordinates in the GitHub release notes.

## Hosted stack

- `docker compose up --build -d` starts Termit + Caddy on port **8080** (HTTP).
- Set `TERMIT_PUBLIC_DOMAIN` for automatic HTTPS on 443.
- See `HOSTED_DEPLOYMENT.md` for auth, volumes, and ops checks.
