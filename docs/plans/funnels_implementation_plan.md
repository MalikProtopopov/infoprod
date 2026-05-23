# Funnels Module — план реализации

Цель: реализовать модуль из `docs/TZ_Funnels_Module.docx` end-to-end с тестами и деплоем.

## Phase A — Backend foundation (модели + миграция)
- [A.1] Модели: LeadMagnet, Funnel, FunnelStep, FunnelEntry, FunnelTrigger, ScheduledMessage
- [A.2] Alembic-миграция: 6 новых таблиц + ALTER tracking_links/products/users
- [A.3] Pydantic schemas: входы/выходы для всех CRUD
- [A.4] Проверка: `python -m py_compile` + `Base.metadata.create_all`

## Phase B — Backend services
- [B.1] services/funnels.py — create, update, start_for_user, cancel_entry, cancel_entries_for_user_on_payment, find_active_entry, reorder_steps
- [B.2] services/funnel_triggers.py — create (нормализация lower), find_by_word, increment_use_count
- [B.3] services/lead_magnets.py — upload (filesystem-storage), send_to_user (с file_id reuse), list_for_product
- [B.4] workers/scheduled_messages.py — process_due (APScheduler, 5min interval, max 100/tick), mark_sent / mark_cancelled / mark_failed

## Phase C — Bot integration
- [C.1] start_with_arg: при funnel_id у tracking_link — funnels.start_for_user
- [C.2] on_text_message: проверка funnel_triggers.find_by_word до обычной обработки
- [C.3] cb_lead: автозапуск product.default_funnel_id
- [C.4] cb_unsubscribe_notifications: users.notifications_enabled=false
- [C.5] funnel_step keyboard: всегда добавляем кнопку «Не присылать напоминания»
- [C.6] Хук в api/payments POST: cancel_entries_for_user_on_payment

## Phase D — API endpoints
- [D.1] /api/funnels: GET list+stats, POST, GET {id}, PATCH, DELETE
- [D.2] /api/funnels/{id}/steps: POST, /api/funnel-steps/{id} PATCH/DELETE, /api/funnels/{id}/reorder POST
- [D.3] /api/funnels/{id}/entries: GET, /api/funnel-entries/{id}/cancel POST
- [D.4] /api/funnels/{id}/stats: GET с агрегацией
- [D.5] /api/lead-magnets: GET, POST (multipart upload), PATCH, DELETE, GET {id}/download
- [D.6] /api/funnel-triggers: GET, POST, PATCH, DELETE
- [D.7] Расширения: PATCH /products включает default_funnel_id; POST /tracking-links включает funnel_id

## Phase E — Backend tests (target ~50)
- [E.1] test_models_funnels — relationships
- [E.2] test_services_funnels — start_for_user (создаёт N scheduled), cancel_entry, cancel_on_payment, double-start idempotent, find_active_entry
- [E.3] test_services_funnel_triggers — case-insensitive, duplicate=409, increment
- [E.4] test_services_lead_magnets — upload filesystem, send_to_user с моком TG, file_id reuse
- [E.5] test_workers_scheduled_messages — due selection, skip unsubscribed, skip inactive entry, mark_sent, mark_failed
- [E.6] test_api_funnels — CRUD + reorder + delete blocked when active entries
- [E.7] test_api_lead_magnets — upload (httpx multipart), validation
- [E.8] test_api_funnel_triggers — duplicate=409, deactivate
- [E.9] test_bot_handlers_funnels — /start с funnel_id, code_word triggers, cb_lead auto-funnel, unsubscribe
- [E.10] test_integration_funnel_flow — полный flow от tracking_link до cancel-on-payment

## Phase F — Frontend (отдельная сессия)
- [F.1] app/(dash)/funnels — список с метриками
- [F.2] app/(dash)/funnels/new + [id]/edit — редактор с drag&drop шагов
- [F.3] app/(dash)/funnels/[id]/entries — подписанные с фильтрами
- [F.4] app/(dash)/lead-magnets — список + upload (drag&drop)
- [F.5] app/(dash)/funnel-triggers — кодовые слова
- [F.6] Интеграция: products/[id] (default_funnel_id, секции воронок/лидмагнитов)
- [F.7] Интеграция: tracking_link create-form — выбор funnel

## Phase G — Frontend tests (отдельная сессия)
- Vitest на каждую новую страницу + MSW handlers

## Phase H — Deploy
- [H.1] rsync на 72.56.72.136
- [H.2] alembic upgrade head внутри db контейнера
- [H.3] docker compose build backend && up -d backend
- [H.4] Smoke-проверка endpoints + Prometheus метрики

---

В этой сессии: **A → B → C → D → E → H** (backend + deploy). Frontend (F, G) — следующая сессия.
