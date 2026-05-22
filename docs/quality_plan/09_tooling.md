# 09. Tooling — полный список инструментов и готовые конфиги

Шпаргалка: что устанавливаем, какие версии, куда кладём конфиги.

## 9.1 Backend Python

### `requirements-dev.txt`

```
# Test runner
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-cov==6.0.0
pytest-xdist==3.6.1
pytest-httpx==0.34.0
pytest-mock==3.14.0

# DB testing
testcontainers[postgres]==4.9.0
factory-boy==3.3.1

# Determinism
freezegun==1.5.1
hypothesis==6.122.3

# Mutation
mutmut==2.5.1

# Lint / format
ruff==0.8.4
mypy==1.13.0
types-passlib==1.7.7
types-python-jose==3.3.4

# Security
bandit==1.8.0
pip-audit==2.7.3

# Coverage on diff (для PR)
diff-cover==9.2.0
```

### `pyproject.toml`

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
extend-exclude = ["alembic/versions/*"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C90", "UP", "ASYNC", "S", "DTZ", "RUF", "SIM"]
ignore = ["B008", "S101"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "S105", "S106", "DTZ005"]
"alembic/**/*.py" = ["E501"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
plugins = ["pydantic.mypy", "sqlalchemy.ext.mypy.plugin"]
exclude = ["alembic/", "scripts/", "tests/"]

[[tool.mypy.overrides]]
module = ["aiogram.*", "factory.*"]
ignore_missing_imports = true

[tool.coverage.run]
source = ["app"]
omit = ["app/main.py", "alembic/*", "*/__init__.py", "scripts/*"]
branch = true
parallel = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
    "@(abc\\.)?abstractmethod",
]
fail_under = 98
precision = 2
show_missing = true

[tool.coverage.html]
directory = "htmlcov"
```

### `pytest.ini`

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
addopts =
    -ra
    --strict-markers
    --strict-config
    --cov=app
    --cov-report=term-missing:skip-covered
    --cov-report=xml:coverage.xml
    --cov-report=html:htmlcov
    --cov-branch
    --no-cov-on-fail
    --tb=short
markers =
    slow: тесты дольше 1 секунды (исключаются с -m "not slow")
    integration: используют реальную БД через testcontainers
    telegram: используют моки Telegram API
    regression: регрессионные тесты под конкретный фикс
filterwarnings =
    error
    ignore::DeprecationWarning:aiogram.*
    ignore::DeprecationWarning:passlib.*
```

## 9.2 Frontend (Next.js)

### `admin/package.json` — devDependencies

```json
{
  "devDependencies": {
    "@playwright/test": "^1.49.1",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "@testing-library/user-event": "^14.5.2",
    "@types/node": "^22.10.5",
    "@vitejs/plugin-react": "^4.3.4",
    "@vitest/coverage-v8": "^2.1.8",
    "@vitest/ui": "^2.1.8",
    "eslint": "^9.18.0",
    "eslint-config-next": "15.1.3",
    "eslint-config-prettier": "^9.1.0",
    "happy-dom": "^15.11.7",
    "msw": "^2.7.0",
    "prettier": "^3.4.2",
    "typescript": "^5.7.2",
    "vitest": "^2.1.8"
  }
}
```

### `admin/vitest.config.ts`

```ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': resolve(__dirname, './') } },
  test: {
    environment: 'happy-dom',
    setupFiles: ['./__tests__/setup.ts'],
    globals: true,
    css: false,
    pool: 'threads',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov', 'json-summary'],
      include: ['app/**', 'lib/**', 'components/**'],
      exclude: [
        '**/*.config.{ts,mjs,js}',
        '__tests__/**',
        '.next/**',
        'node_modules/**',
        '**/layout.tsx',  // boot only
      ],
      thresholds: {
        lines: 98,
        functions: 98,
        branches: 95,
        statements: 98,
      },
    },
  },
});
```

### `admin/tsconfig.json` — добавки

```json
{
  "compilerOptions": {
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "exactOptionalPropertyTypes": false,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  }
}
```

### `admin/eslint.config.mjs`

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
      'react/no-array-index-key': 'warn',
      'no-console': ['warn', { allow: ['warn', 'error'] }],
    },
  },
];
```

### `admin/.prettierrc`

```json
{
  "semi": true,
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2,
  "arrowParens": "always",
  "endOfLine": "lf"
}
```

### `admin/.prettierignore`

```
.next/
node_modules/
coverage/
build/
public/
```

## 9.3 E2E

### `e2e/package.json`

```json
{
  "name": "infobizbot-e2e",
  "private": true,
  "scripts": {
    "test": "playwright test",
    "test:ui": "playwright test --ui",
    "report": "playwright show-report"
  },
  "devDependencies": {
    "@playwright/test": "^1.49.1",
    "typescript": "^5.7.2",
    "@types/node": "^22.10.5"
  }
}
```

### `e2e/playwright.config.ts`

См. файл `03_e2e_tests.md` § 3.7.

## 9.4 Pre-commit

### `.pre-commit-config.yaml`

См. файл `06_ci_cd.md` § 6.2.

Установка:
```bash
pip install pre-commit==4.0.1
pre-commit install
pre-commit install --hook-type commit-msg  # для conventional commits, опционально
```

## 9.5 CI / GitHub

### `.github/workflows/ci.yml` — главный pipeline

См. `06_ci_cd.md` § 6.1.

### `.github/workflows/codeql.yml`

См. `06_ci_cd.md` § 6.8.

### `.github/workflows/gitleaks.yml`

См. `07_audit_security.md` § 7.4.2.

### `.github/dependabot.yml`

См. `06_ci_cd.md` § 6.7.

### `.codecov.yml`

См. `06_ci_cd.md` § 6.6.

## 9.6 Logging libraries

### Python — `requirements.txt`

```
structlog==24.4.0
python-json-logger==2.0.7
opentelemetry-distro==0.50b0
opentelemetry-exporter-otlp==1.29.0
opentelemetry-instrumentation-fastapi==0.50b0
opentelemetry-instrumentation-sqlalchemy==0.50b0
opentelemetry-instrumentation-httpx==0.50b0
opentelemetry-instrumentation-asyncpg==0.50b0
prometheus-fastapi-instrumentator==7.0.0
prometheus-client==0.21.1
sentry-sdk[fastapi]==2.20.0
```

### Frontend — `admin/package.json` dependencies

```json
{
  "@sentry/nextjs": "^8.49.0"
}
```

## 9.7 Observability — docker images

```yaml
loki: grafana/loki:3.3.2
promtail: grafana/promtail:3.3.2
grafana: grafana/grafana:11.4.0
prometheus: prom/prometheus:v3.0.1
alertmanager: prom/alertmanager:v0.27.0
tempo: grafana/tempo:2.7.0
nginx-exporter: nginx/nginx-prometheus-exporter:1.4.0
postgres-exporter: prometheuscommunity/postgres-exporter:v0.16.0
node-exporter: prom/node-exporter:v1.8.2
blackbox-exporter: prom/blackbox-exporter:v0.25.0
mockoon: mockoon/cli:9.2.0
```

## 9.8 Структура папок после внедрения

```
infobizbot/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── codeql.yml
│   │   └── gitleaks.yml
│   └── dependabot.yml
├── .codecov.yml
├── .pre-commit-config.yaml
├── .gitignore
├── docker-compose.yml
├── docker-compose.test.yml
├── docker-compose.observability.yml      # отдельный compose для логов/метрик
├── docs/
│   ├── PROJECT_CONTEXT.md
│   ├── analytics_plan/                   # уже есть
│   ├── quality_plan/                     # текущий план
│   └── runbooks/                         # playbooks для дежурного
│       ├── db_down.md
│       ├── bot_silent.md
│       └── sentry_5xx_alert.md
├── backend/
│   ├── app/                              # production code
│   ├── alembic/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── factories.py
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── property/
│   │   ├── regressions/
│   │   └── fixtures/
│   ├── scripts/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml
│   ├── pytest.ini
│   └── Dockerfile
├── admin/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── __tests__/
│   │   ├── setup.ts
│   │   ├── mocks/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── pages/
│   │   └── regressions/
│   ├── eslint.config.mjs
│   ├── .prettierrc
│   ├── vitest.config.ts
│   ├── package.json
│   ├── tsconfig.json
│   └── Dockerfile
├── e2e/
│   ├── tests/
│   ├── fixtures/
│   ├── telegram-mock.json
│   ├── playwright.config.ts
│   ├── global-setup.ts
│   ├── package.json
│   └── tsconfig.json
├── nginx/
│   ├── nginx.conf
│   └── ssl/
├── observability/
│   ├── loki-config.yml
│   ├── promtail-config.yml
│   ├── prometheus.yml
│   ├── tempo.yml
│   ├── alertmanager.yml
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           │   ├── loki.yml
│           │   ├── prometheus.yml
│           │   └── tempo.yml
│           ├── dashboards/
│           │   ├── overview.json
│           │   ├── logs.json
│           │   ├── bot-activity.json
│           │   └── database.json
│           └── alerting/
│               └── rules.yml
└── certbot/                              # уже есть
```

## 9.9 Команды на каждый день

```bash
# Backend
cd backend
pytest                              # все тесты
pytest -n 4                         # параллельно
pytest tests/unit/services -v       # только unit
pytest --cov-report=html            # html-отчёт по покрытию
pytest -k "test_grant"              # по имени
ruff check . && ruff format --check .
mypy app
bandit -r app -lll

# Frontend
cd admin
npm test                            # vitest run
npm run test:watch                  # watch-mode
npm run test:cov                    # coverage
npm run test:ui                     # UI vitest
npm run lint
npm run type-check

# E2E
cd e2e
npm test
npm run test:ui                     # interactive
npm run report                      # последний отчёт

# Pre-commit вручную на staged-файлах
pre-commit run

# Pre-commit на всех файлах (первый запуск)
pre-commit run --all-files
```

## 9.10 Что НЕ выбрали и почему

| Альтернатива | Почему отвергнута |
|--------------|-------------------|
| Jest вместо Vitest | Vitest нативный для Vite/TS, в 2× быстрее, единый конфиг с dev-сервером |
| Cypress вместо Playwright | Playwright лучше для multi-browser (Firefox + Safari), Trace Viewer мощнее |
| Black + isort вместо ruff | Ruff = 10–100× быстрее, делает всё в одном инструменте |
| Datadog/NewRelic вместо self-hosted Grafana | Платно $$$; self-hosted даёт control + бесплатно |
| ELK (Elastic + Logstash + Kibana) вместо Loki | Loki — 10× дешевле по storage, индексирует только labels |
| Honeycomb для traces | Платно; Tempo бесплатный |
| Cloud Sentry vs self-hosted Sentry | Free tier 5k events/мес достаточно для старта; self-host позже |
| Selenium вместо Playwright | Устарел, медленнее, хуже API |
| Tox вместо одного pytest | Не нужен — один Python target, один venv |

## 9.11 Стоимость инфраструктуры

| Инструмент | Стоимость |
|-----------|-----------|
| GitHub Actions | бесплатно (2000 мин/мес для приватного) |
| Codecov | бесплатно для open-source / $10/мес private |
| Sentry | free tier 5k events, потом $26/мес |
| Loki + Grafana + Prometheus | бесплатно, self-hosted |
| Tempo | бесплатно, self-hosted |
| Server (доп. RAM на observability) | +$5–10/мес или докупить 4 GB |

Total: **$0–35 в месяц** на старте.
