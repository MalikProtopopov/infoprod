# 05. Админ-панель (Next.js 15)

## Стек
- Next.js 15 (App Router), TypeScript, Tailwind CSS.
- Минимум зависимостей: `clsx`, `swr` (для запросов), без тяжёлых UI‑либ. Простой собственный набор компонентов (`Button`, `Input`, `Table`, `Modal`).
- Аутентификация — кука JWT, ставится backend‑ом. На клиенте только проверка через `GET /api/auth/me`.
- Production build — `next build && next start` (или standalone).

## Карта страниц
```
/login                  — форма входа
/                       — редирект на /bots
/bots                   — список ботов + кнопка «Добавить»
/channels               — список каналов
/products               — список продуктов
/products/new
/products/[id]/edit
/users                  — таблица + поиск
/users/[id]             — карточка пользователя (заметки, заявки, платежи, подписки)
/payments               — список + кнопка «Добавить платёж» (модалка с выбором юзера/продукта/периода)
/subscriptions          — таблица с фильтром active/expired/revoked
/account                — смена пароля + выход
```

## Лейаут
Боковое меню с разделами и шапка с именем администратора. Защищённые роуты — middleware проверяет, что есть кука и пользователь авторизован (или просто SWR `/auth/me` с редиректом на /login).

## API‑клиент (`lib/api.ts`)
- `fetch` к `${API_URL}/api/...` с `credentials: 'include'`.
- Обёртки `apiGet`, `apiPost`, `apiPatch`, `apiDelete`.

## Стилистика
Серая нейтральная палитра, Tailwind, без анимаций. Цель — функциональность, не визуал.

## Production
- `next.config.js` → `output: 'standalone'`.
- В `Dockerfile` собираем standalone, запускаем `node server.js`.
- `NEXT_PUBLIC_API_URL` берётся из env на этапе билда (или из same-origin через nginx — предпочтительный вариант: `/api/*` на том же origin).
