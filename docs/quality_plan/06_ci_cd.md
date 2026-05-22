# 06. CI/CD — GitHub Actions, pre-commit, branch protection

## 6.1 GitHub Actions — основной pipeline

Файл: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  # ─────────────────────────────────────────────────────
  backend-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12', cache: pip }
      - run: pip install -r backend/requirements-dev.txt
      - run: ruff check backend
      - run: ruff format --check backend
      - run: mypy backend/app --strict
      - run: bandit -q -r backend/app -lll      # high severity only

  backend-test:
    runs-on: ubuntu-latest
    services:
      docker:
        image: docker:24
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12', cache: pip }
      - run: pip install -r backend/requirements.txt -r backend/requirements-dev.txt
      - run: cd backend && pytest --cov-report=xml --cov-report=term -n 4
      - uses: codecov/codecov-action@v5
        with:
          files: ./backend/coverage.xml
          flags: backend
          fail_ci_if_error: true

  # ─────────────────────────────────────────────────────
  frontend-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22', cache: npm, cache-dependency-path: admin/package-lock.json }
      - run: cd admin && npm ci
      - run: cd admin && npm run lint
      - run: cd admin && npm run type-check
      - run: cd admin && npm run format:check

  frontend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22', cache: npm, cache-dependency-path: admin/package-lock.json }
      - run: cd admin && npm ci
      - run: cd admin && npm run test:cov
      - uses: codecov/codecov-action@v5
        with:
          files: ./admin/coverage/lcov.info
          flags: frontend
          fail_ci_if_error: true

  # ─────────────────────────────────────────────────────
  e2e:
    runs-on: ubuntu-latest
    needs: [backend-test, frontend-test]
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22', cache: npm, cache-dependency-path: e2e/package-lock.json }
      - run: cd e2e && npm ci
      - run: cd e2e && npx playwright install --with-deps chromium firefox
      - run: docker compose -f docker-compose.test.yml up -d --build --wait
      - run: cd e2e && npx playwright test
      - if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: e2e/playwright-report/
      - if: always()
        run: docker compose -f docker-compose.test.yml down -v

  # ─────────────────────────────────────────────────────
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install pip-audit
      - run: pip-audit -r backend/requirements.txt --strict
      - uses: actions/setup-node@v4
        with: { node-version: '22', cache: npm, cache-dependency-path: admin/package-lock.json }
      - run: cd admin && npm audit --omit=dev --audit-level=high
      - name: Trivy filesystem scan
        uses: aquasecurity/trivy-action@0.28.0
        with:
          scan-type: fs
          severity: CRITICAL,HIGH
          exit-code: 1
          ignore-unfixed: true

  # ─────────────────────────────────────────────────────
  build-images:
    runs-on: ubuntu-latest
    needs: [backend-lint, backend-test, frontend-lint, frontend-test, security]
    if: github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: ./backend
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/backend:latest
            ghcr.io/${{ github.repository }}/backend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - uses: docker/build-push-action@v6
        with:
          context: ./admin
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/admin:latest
            ghcr.io/${{ github.repository }}/admin:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ─────────────────────────────────────────────────────
  deploy:
    runs-on: ubuntu-latest
    needs: [build-images, e2e]
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
      - uses: actions/checkout@v4
      - name: Deploy via SSH
        env:
          SSH_PRIVATE_KEY: ${{ secrets.SSH_PRIVATE_KEY }}
          SERVER: ${{ secrets.SERVER_HOST }}
        run: |
          mkdir -p ~/.ssh
          echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_ed25519
          chmod 600 ~/.ssh/id_ed25519
          ssh -o StrictHostKeyChecking=no root@$SERVER bash -s <<'EOF'
            cd /opt/infobizbot
            git fetch && git checkout main && git pull --ff-only
            docker compose pull
            docker compose up -d
            docker compose exec -T backend alembic upgrade head
          EOF
      - name: Notify Sentry of release
        uses: getsentry/action-release@v1
        with:
          environment: production
          version: ${{ github.sha }}
        env:
          SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
          SENTRY_ORG:        ${{ secrets.SENTRY_ORG }}
          SENTRY_PROJECT:    ${{ secrets.SENTRY_PROJECT }}
```

## 6.2 Pre-commit hooks — `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-yaml
      - id: check-toml
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix]
        files: ^backend/
      - id: ruff-format
        files: ^backend/

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, sqlalchemy, structlog]
        files: ^backend/app/
        args: [--strict, --ignore-missing-imports]

  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v4.0.0-alpha.8
    hooks:
      - id: prettier
        files: ^admin/.*\.(ts|tsx|js|jsx|json|md|yml|yaml)$
        exclude: ^admin/(\.next|node_modules)/

  - repo: local
    hooks:
      - id: eslint
        name: eslint
        entry: bash -c 'cd admin && npm run lint'
        language: system
        files: ^admin/.*\.(ts|tsx)$
        pass_filenames: false
```

Установка: `pip install pre-commit && pre-commit install`.

## 6.3 Ruff config — `backend/pyproject.toml`

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # bugbear
    "C90", # mccabe complexity
    "UP",  # pyupgrade
    "ASYNC",
    "S",   # bandit security
    "DTZ", # datetime tz-aware
    "RUF",
]
ignore = [
    "B008",  # FastAPI Depends(...) в дефолтных значениях — это нормально
    "S101",  # assert (нужен в тестах)
]
[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "S105", "S106"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy", "sqlalchemy.ext.mypy.plugin"]
exclude = ["alembic/", "scripts/"]
```

## 6.4 ESLint + Prettier — `admin/`

`admin/eslint.config.mjs`:
```js
import next from 'eslint-config-next';
import prettier from 'eslint-config-prettier';

export default [
  ...next,
  prettier,
  {
    rules: {
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'warn',
      'react-hooks/exhaustive-deps': 'error',
    },
  },
];
```

`admin/.prettierrc`:
```json
{
  "semi": true,
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2,
  "arrowParens": "always"
}
```

## 6.5 Branch protection (GitHub Settings)

`Settings → Branches → Add rule` для `main`:

- ✅ Require pull request before merging
  - Require approvals: 1
  - Dismiss stale reviews
- ✅ Require status checks to pass:
  - `backend-lint`
  - `backend-test`
  - `frontend-lint`
  - `frontend-test`
  - `e2e`
  - `security`
- ✅ Require branches to be up to date before merging
- ✅ Require conversation resolution
- ✅ Require signed commits (опционально)
- ✅ Do not allow bypassing the above settings

## 6.6 Codecov

Регистрация на codecov.io → подключить репо → положить `CODECOV_TOKEN` в secrets.

В корне `.codecov.yml`:

```yaml
coverage:
  status:
    project:
      backend:
        target: 98%
        threshold: 0.5%
        paths: ["backend/app/"]
      frontend:
        target: 98%
        threshold: 0.5%
        paths: ["admin/"]
    patch:
      default:
        target: 95%
```

Любой PR, который **снижает** coverage больше чем на 0.5%, блокируется.

## 6.7 Dependabot — `.github/dependabot.yml`

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /backend
    schedule: { interval: weekly }
    groups:
      python-minor:
        update-types: [minor, patch]
  - package-ecosystem: npm
    directory: /admin
    schedule: { interval: weekly }
    groups:
      node-minor:
        update-types: [minor, patch]
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: monthly }
  - package-ecosystem: docker
    directory: /backend
    schedule: { interval: weekly }
  - package-ecosystem: docker
    directory: /admin
    schedule: { interval: weekly }
```

## 6.8 CodeQL (опционально, но бесплатно)

`.github/workflows/codeql.yml`:
```yaml
name: CodeQL
on:
  schedule:
    - cron: '0 0 * * 1'
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions: { security-events: write, contents: read }
    strategy:
      matrix:
        language: [python, javascript]
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with: { languages: ${{ matrix.language }} }
      - uses: github/codeql-action/analyze@v3
```

## 6.9 Деплой стратегия

**Сейчас**: docker compose down/up на одном сервере.

**Цель Phase 1**: rolling-update без даунтайма.
- Backend: 2 реплики за nginx (round-robin), graceful shutdown 30s.
- Admin: 2 реплики.
- При деплое: `docker compose up -d --no-deps backend` — поднимет вторую, потом nginx балансирует.

**Цель Phase 2** (когда вырастем): kubernetes (k3s) с readiness probes.

## 6.10 Чек-лист CI/CD

- [ ] `.github/workflows/ci.yml` со всеми 7 jobs
- [ ] `requirements-dev.txt` с pytest/ruff/mypy/bandit
- [ ] `pyproject.toml` с ruff/mypy
- [ ] `.pre-commit-config.yaml` + установить `pre-commit install`
- [ ] `eslint.config.mjs` + `.prettierrc`
- [ ] `.codecov.yml`
- [ ] `.github/dependabot.yml`
- [ ] CodeQL workflow
- [ ] Secrets в GitHub:
  - `SSH_PRIVATE_KEY` (для деплоя)
  - `SERVER_HOST`
  - `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`
  - `CODECOV_TOKEN`
- [ ] Branch protection включён на `main`
- [ ] GHCR права для push образов
