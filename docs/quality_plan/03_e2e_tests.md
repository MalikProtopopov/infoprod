# 03. E2E — Playwright + docker compose stack

E2E проверяет систему **целиком**: бот + бэкенд + БД + nginx + админка через реальный браузер. Никаких моков на уровне HTTP. Только Telegram API заменён локальным **mock server** (потому что писать в реальный Telegram нельзя в CI).

## 3.1 Стек

| Инструмент | Версия | Назначение |
|-----------|-------|-----------|
| **@playwright/test** | 1.49+ | Test runner + reporter + trace viewer |
| **mockoon** или **wiremock** | 9.x / 3.x | Mock-сервер Telegram API |

## 3.2 Архитектура

```
                 ┌────────────────────────────┐
                 │     playwright runner       │
                 │  (Chrome/Firefox/Mobile)   │
                 └─────────────┬──────────────┘
                               │ HTTPS (Playwright ignoreHTTPSErrors)
                  ┌────────────▼────────────┐
                  │     docker-compose.test │
                  │  (точно production топ.)│
                  └────────────┬────────────┘
                               │
       ┌───────────────────────┼────────────────────────┐
       ▼                       ▼                        ▼
   nginx          backend (FastAPI+aiogram)         admin (Next.js)
                       │
                       │  ❶ TELEGRAM_BASE_URL=http://tg-mock:1080/bot{token}
                       ▼
              ┌────────────────────────┐
              │  tg-mock (mockoon)     │
              │  отвечает на getMe,    │
              │  sendMessage и т.п.    │
              └────────────────────────┘
```

Ключевая идея: **подменить переменную окружения** в backend на `TELEGRAM_BASE_URL=http://tg-mock:1080` и aiogram будет ходить туда. Mockoon отдаёт детерминированные JSON-ответы.

## 3.3 `docker-compose.test.yml`

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: test
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    tmpfs:
      - /var/lib/postgresql/data    # in-memory, быстрее
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test"]
      interval: 2s
      retries: 30

  tg-mock:
    image: mockoon/cli:9.2.0
    command: ["-d", "/data/telegram.json", "-p", "1080"]
    volumes:
      - ./e2e/telegram-mock.json:/data/telegram.json:ro
    ports:
      - "1080"

  backend:
    build: ./backend
    depends_on:
      db:
        condition: service_healthy
      tg-mock:
        condition: service_started
    environment:
      DATABASE_URL: postgresql+asyncpg://test:test@db:5432/test
      JWT_SECRET: e2e-secret-32chars-aaaaaaaaaaaaaaaaaa
      ADMIN_USERNAME: admin
      ADMIN_PASSWORD: e2etest
      CORS_ORIGINS: https://localhost
      COOKIE_SECURE: "false"
      # Подменяем base URL aiogram'а
      TELEGRAM_API_SERVER: http://tg-mock:1080
    command: >
      sh -c "alembic upgrade head &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000"

  admin:
    build: ./admin
    depends_on: [backend]

  nginx:
    image: nginx:alpine
    depends_on: [admin, backend]
    ports:
      - "8443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl-test:/etc/nginx/ssl:ro
```

Запуск:
```bash
docker compose -f docker-compose.test.yml up -d --build --wait
```

## 3.4 Подключить кастомный Telegram base URL

В `app/services/telegram.py` и `bot/manager.py` aiogram использует `Bot(token=...)`. Чтобы перенаправить:

```python
# app/core/config.py
class Settings(BaseSettings):
    ...
    telegram_api_server: str | None = None  # для тестов
```

```python
# app/bot/manager.py — в _start_bot
from aiogram.client.telegram import TelegramAPIServer

properties = DefaultBotProperties(parse_mode=ParseMode.HTML)
if settings.telegram_api_server:
    properties = DefaultBotProperties(
        parse_mode=ParseMode.HTML,
        # API base override
    )
    session = AiohttpSession(api=TelegramAPIServer.from_base(settings.telegram_api_server))
    bot = Bot(token=bot_row.token, session=session, default=properties)
else:
    bot = Bot(token=bot_row.token, default=properties)
```

## 3.5 `e2e/telegram-mock.json` (mockoon-формат)

Минимальный набор маршрутов: getMe, sendMessage, createChatInviteLink, banChatMember, getChat, getChatMember, getUpdates (на случай polling), deleteWebhook.

Пример фрагмента:
```json
{
  "routes": [
    {
      "method": "post",
      "endpoint": "bot::token::/getMe",
      "responses": [{
        "statusCode": 200,
        "body": "{\"ok\":true,\"result\":{\"id\":12345,\"is_bot\":true,\"username\":\"e2ebot\",\"first_name\":\"E2E\"}}"
      }]
    },
    {
      "method": "post",
      "endpoint": "bot::token::/sendMessage",
      "responses": [{
        "statusCode": 200,
        "body": "{\"ok\":true,\"result\":{\"message_id\":1,\"date\":1700000000,\"chat\":{\"id\":1,\"type\":\"private\"}}}"
      }]
    },
    {
      "method": "post",
      "endpoint": "bot::token::/createChatInviteLink",
      "responses": [{
        "statusCode": 200,
        "body": "{\"ok\":true,\"result\":{\"invite_link\":\"https://t.me/+e2eINVITE\"}}"
      }]
    }
  ]
}
```

## 3.6 Структура Playwright

```
e2e/
├── playwright.config.ts
├── docker-compose.test.yml
├── telegram-mock.json
├── fixtures/
│   ├── auth.ts           # авторизованная страница как fixture
│   ├── db.ts             # утилиты «вставь в БД через прямой SQL»
│   └── tg.ts             # утилиты «отправь /start от имени user в mock-bot»
├── tests/
│   ├── auth.spec.ts
│   ├── bots.spec.ts
│   ├── channels.spec.ts
│   ├── products.spec.ts
│   ├── tracking-links.spec.ts
│   ├── payments.spec.ts
│   ├── subscriptions.spec.ts
│   ├── leads.spec.ts
│   ├── sources.spec.ts
│   └── full-flow.spec.ts    # самый главный — от рекламы до канала
└── global-setup.ts
```

## 3.7 `playwright.config.ts`

```ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
    ['github'],
  ],
  use: {
    baseURL: process.env.BASE_URL || 'https://localhost:8443',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    ignoreHTTPSErrors: true,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox',  use: { ...devices['Desktop Firefox'] } },
    { name: 'mobile',   use: { ...devices['Pixel 7'] } },
  ],
  globalSetup: './global-setup.ts',
});
```

## 3.8 Главный E2E — full purchase flow

```ts
// e2e/tests/full-flow.spec.ts
import { test, expect } from '@playwright/test';
import { resetDb, addBotDirect, addChannelDirect } from '../fixtures/db';
import { sendStartCommand, sendCallbackQuery } from '../fixtures/tg';

test.describe('Full purchase flow', () => {
  test.beforeEach(async () => { await resetDb(); });

  test('реклама → бот → заявка → оплата → доступ → истечение', async ({ page }) => {
    // 1) Прямо в БД создаём бота + канал (минуем UI Telegram-проверки)
    const botId      = await addBotDirect();
    const channelId  = await addChannelDirect(botId);

    // 2) Логин в админке
    await page.goto('/login');
    await page.getByLabel('Логин').fill('admin');
    await page.getByLabel('Пароль').fill('e2etest');
    await page.getByRole('button', { name: 'Войти' }).click();
    await expect(page).toHaveURL('/');

    // 3) Создаём продукт через UI
    await page.goto('/products');
    await page.getByRole('button', { name: /добавить продукт/i }).click();
    await page.getByLabel('Код').fill('e2eprod');
    await page.getByLabel('Название').fill('E2E Product');
    await page.locator('select').first().selectOption({ label: /Channel/ });
    await page.locator('input[value="0"]').first().fill('1000');
    await page.getByRole('button', { name: 'Сохранить' }).click();
    await expect(page.getByText('e2eprod')).toBeVisible();

    // 4) Создаём трекинговую ссылку через UI
    await page.getByRole('link', { name: 'Ссылки' }).first().click();
    await page.getByRole('button', { name: /создать ссылку с источником/i }).click();
    await page.getByLabel(/источник/i).fill('instagram');
    await page.getByRole('button', { name: 'Сгенерировать' }).click();
    const slug = await page.locator('[class*="font-mono"]').first().textContent();
    expect(slug).toMatch(/^[A-Za-z0-9]{8}$/);

    // 5) Симулируем клик клиента: посылаем /start <slug> через моковый Telegram
    await sendStartCommand({ tgUserId: 999, slug: slug!, firstName: 'TestClient' });
    await page.waitForTimeout(500);  // даём боту обработать

    // 6) Симулируем "Оставить заявку"
    await sendCallbackQuery({ tgUserId: 999, data: `lead:${await getCreatedProductId()}` });

    // 7) Заявка появилась в админке
    await page.goto('/leads');
    await expect(page.getByText('TestClient')).toBeVisible();
    await expect(page.locator('text=новая')).toBeVisible();

    // 8) Создаём платёж
    await page.goto('/payments');
    await page.getByRole('button', { name: /добавить платёж/i }).click();
    await page.getByPlaceholder(/имя/i).fill('TestClient');
    await page.locator('button:has-text("TestClient")').click();
    await page.locator('select').nth(0).selectOption('e2eprod');  // продукт
    await page.locator('select').nth(1).selectOption('3');         // период
    await page.getByRole('button', { name: 'Сохранить' }).click();
    await expect(page.getByText('1 000')).toBeVisible();  // сумма

    // 9) Проверяем что подписка создалась
    await page.goto('/subscriptions');
    await expect(page.getByText('активна')).toBeVisible();

    // 10) Проверяем что в /sources видно instagram
    await page.goto('/sources');
    await expect(page.getByText('instagram')).toBeVisible();
  });
});
```

## 3.9 Список E2E-сценариев («golden flows»)

| # | Файл | Что проверяет |
|---|------|---------------|
| 1 | `auth.spec.ts` | Логин валид/невалид, logout, redirect /login → / при наличии куки |
| 2 | `bots.spec.ts` | Добавление бота через UI с моком Telegram, активация/деактивация |
| 3 | `channels.spec.ts` | Добавление канала, FK-ошибка при удалении бота с каналом |
| 4 | `products.spec.ts` | CRUD продукта, коллизия code ↔ tracking_link.slug |
| 5 | `tracking-links.spec.ts` | Создание, копирование URL, QR (скачивается PNG ≥500 байт) |
| 6 | `payments.spec.ts` | Платёж выдаёт invite, удаление платежа отзывает подписку |
| 7 | `subscriptions.spec.ts` | Отзыв вручную, продление вручную с TTL вылетел → новый invite |
| 8 | `leads.spec.ts` | Смена статуса заявки, авто-paid при платеже |
| 9 | `sources.spec.ts` | Фильтры периода, переключение группировки, **не зацикливает запросы** |
| 10 | `full-flow.spec.ts` | end-to-end сценарий выше |

## 3.10 Параллелизация и стабильность

- `fullyParallel: true` — каждый тест на своей странице.
- В `beforeEach` чистим БД (TRUNCATE) — но это глобально, поэтому либо последовательно по файлам, либо отдельная БД на worker через `process.env.TEST_WORKER_INDEX`.
- Для **визуальной стабильности** — `toHaveScreenshot()` с pixel-tolerance.

## 3.11 Telemetry от Playwright

- `--reporter=html` → отчёт с trace и видео по падениям.
- `playwright show-report` → открыть в браузере.
- В CI — артефакт `playwright-report/` + `test-results/` (видео + trace).

## 3.12 Чек-лист E2E

- [ ] Добавить aiogram-override через `TELEGRAM_API_SERVER` env
- [ ] `docker-compose.test.yml` с `tmpfs` postgres, mockoon, без сертификатов let's encrypt (использовать self-signed)
- [ ] `telegram-mock.json` со всеми нужными endpoints
- [ ] `playwright.config.ts` + global setup
- [ ] 10 spec-файлов
- [ ] `resetDb()` фикстура (TRUNCATE всех таблиц или migrate from scratch)
- [ ] `sendStartCommand` / `sendCallbackQuery` utils
- [ ] CI job: `e2e` после `unit` и `build`
- [ ] Trace + screenshot + video на падение
- [ ] Visual regression на главных страницах (опционально)
