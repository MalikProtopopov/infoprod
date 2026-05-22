# 07. Audit log, RBAC, security testing, secrets

## 7.1 Audit log — кто что когда изменил

### 7.1.1 Таблица `audit_log`

Миграция:

```sql
CREATE TABLE audit_log (
  id            bigserial PRIMARY KEY,
  ts            timestamptz NOT NULL DEFAULT now(),
  actor_type    text NOT NULL,   -- 'admin' | 'system' | 'bot'
  admin_id      bigint NULL REFERENCES admins(id) ON DELETE SET NULL,
  request_id    text NULL,
  action        text NOT NULL,   -- 'payment.created' | 'bot.deleted' | ...
  entity_type   text NULL,       -- 'payment' | 'bot' | 'subscription' | ...
  entity_id     bigint NULL,
  diff          jsonb NULL,      -- {before: {...}, after: {...}} или {fields_changed: [...]}
  client_ip     text NULL,
  user_agent    text NULL
);
CREATE INDEX audit_log_admin_ts  ON audit_log(admin_id, ts DESC);
CREATE INDEX audit_log_action_ts ON audit_log(action, ts DESC);
CREATE INDEX audit_log_entity    ON audit_log(entity_type, entity_id);
```

### 7.1.2 Сервис

```python
# app/services/audit.py
async def emit_audit(
    session: AsyncSession,
    *,
    action: str,
    actor_type: str = "admin",
    admin_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    diff: dict | None = None,
    request: Request | None = None,
) -> None:
    log_row = AuditLog(
        action=action,
        actor_type=actor_type,
        admin_id=admin_id,
        entity_type=entity_type,
        entity_id=entity_id,
        diff=diff,
        request_id=structlog.contextvars.get_contextvars().get("request_id"),
        client_ip=_get_client_ip(request) if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    session.add(log_row)
    # Не commit — оставляем для основной транзакции
```

### 7.1.3 Декоратор `@audit`

Для одного коммита и аудита:

```python
# app/api/audit_dep.py
def audit(action: str, entity_type: str | None = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request = None, admin: Admin = None, session: AsyncSession = None, **kwargs):
            result = await func(*args, request=request, admin=admin, session=session, **kwargs)
            entity_id = None
            if hasattr(result, "id"):
                entity_id = result.id
            elif isinstance(result, dict) and "id" in result:
                entity_id = result["id"]
            await emit_audit(
                session, action=action, admin_id=admin.id,
                entity_type=entity_type, entity_id=entity_id,
                request=request,
            )
            await session.commit()
            return result
        return wrapper
    return decorator
```

Применять на mutating endpoints:

```python
@router.post("/payments", response_model=PaymentOut)
@audit(action="payment.created", entity_type="payment")
async def create_payment(payload, admin, session, request): ...
```

### 7.1.4 Что попадает в audit

| Действие | action |
|----------|--------|
| Логин админа | `auth.login_success` |
| Смена пароля | `admin.password_changed` |
| Бот добавлен/удалён | `bot.created` / `bot.deleted` |
| Канал добавлен/удалён | `channel.created` / `channel.deleted` |
| Продукт CRUD | `product.created` / `product.updated` / `product.deleted` |
| Tracking-link CRUD | `tracking_link.created` / `tracking_link.deactivated` / `tracking_link.deleted` |
| Платёж создан/удалён | `payment.created` / `payment.deleted` |
| Подписка отозвана/продлена | `subscription.revoked` / `subscription.extended_manual` |
| Изменение профиля юзера | `user.updated` (diff: какие поля изменились) |
| Изменение статуса заявки | `lead.status_changed` (diff: {from, to}) |

### 7.1.5 UI просмотра audit log

Страница `/audit` (для главного админа):
- Таблица: ts / actor (admin username) / action / entity / IP / request_id (link to Grafana)
- Фильтры: за период, по action, по admin

## 7.2 RBAC — роли (Phase 4)

Сейчас один тип `admin`. План — три роли:

| Роль | Доступ |
|------|--------|
| `super_admin` | всё включая удаление ботов, audit log, смена пароля других |
| `admin` | CRUD продуктов/каналов/ботов, видит audit своих действий |
| `operator` | только: заявки, платежи, юзеры (без CRUD каталога) |

Миграция:
```sql
ALTER TABLE admins
  ADD COLUMN role text NOT NULL DEFAULT 'admin' CHECK (role IN ('super_admin','admin','operator')),
  ADD COLUMN full_name text NULL,
  ADD COLUMN is_active boolean NOT NULL DEFAULT true;
```

Декоратор проверки:

```python
def require_role(*roles: str):
    async def dep(admin: Admin = Depends(current_admin)) -> Admin:
        if admin.role not in roles:
            raise HTTPException(403, "Недостаточно прав")
        return admin
    return dep

# применение
@router.delete("/bots/{bot_id}")
async def delete_bot(_: Admin = Depends(require_role("super_admin"))): ...
```

## 7.3 Security testing

### 7.3.1 Bandit — статический анализ Python

```bash
bandit -r backend/app -lll  # only high severity
```

В CI блокирует на `HIGH+` находках.

### 7.3.2 pip-audit — известные CVE

```bash
pip-audit -r backend/requirements.txt --strict
```

### 7.3.3 npm audit — node deps

```bash
cd admin && npm audit --omit=dev --audit-level=high
```

### 7.3.4 Trivy — сканирование Docker-образов

```bash
trivy image ghcr.io/owner/repo/backend:latest --severity CRITICAL,HIGH
trivy image ghcr.io/owner/repo/admin:latest --severity CRITICAL,HIGH
```

### 7.3.5 OWASP ZAP — динамический сканер (для прода)

Ручной запуск против stage:

```bash
docker run -t owasp/zap2docker-stable zap-baseline.py -t https://grammy.mediann.dev/
```

Ищет: missing security headers, XSS, SQL inj, CSRF.

### 7.3.6 Sqlmap (опционально) — целенаправленный SQL injection

```bash
sqlmap -u "https://grammy.mediann.dev/api/users?q=test" --cookie="access_token=..." --batch --risk=1 --level=2
```

### 7.3.7 Что проверять руками

| Уязвимость | Как проверить |
|------------|---------------|
| SQL injection | Pydantic + SQLAlchemy parameterized queries — должно быть невозможно |
| XSS | React автоматически escape'ит. Проверить что нигде нет `dangerouslySetInnerHTML` |
| CSRF | SameSite=Lax + cookie + проверка origin → должно быть закрыто |
| IDOR (Insecure Direct Object Reference) | Может ли `operator` дёргать `DELETE /api/payments/{другого_админа}`? Тест в E2E |
| Open redirect | Нет открытых redirect endpoints |
| Brute force login | Rate-limit 10/мин (есть) |
| Secrets в логах | Тест `_mask_secrets_processor` |
| JWT в localStorage | Нет — мы используем HttpOnly cookie |
| File upload | Сейчас нет загрузки файлов. Когда появится — проверять MIME, размер, антивирус |

## 7.4 Secrets management

### 7.4.1 Текущий рисунок

- `.env` на сервере, chmod 600.
- В коде нет хардкода (проверим `gitleaks`).
- В CI секреты — GitHub Actions Secrets.

### 7.4.2 Gitleaks

`.github/workflows/gitleaks.yml`:
```yaml
name: gitleaks
on:
  pull_request:
  push:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}   # optional
```

Сканирует историю на токены, ключи API, пароли.

### 7.4.3 Ротация ключей

- **JWT_SECRET** — раз в 90 дней. После ротации — `docker compose restart backend` (все пользователи разлогинятся).
- **POSTGRES_PASSWORD** — раз в год.
- **Bot tokens** — при компрометации, через @BotFather → revoke + новая запись в БД.
- **SSH ключи к серверу** — раз в 6 мес.
- **Let's Encrypt cert** — авто, не ротируется руками.

### 7.4.4 Backups секретов

- `.env` файл backuped в зашифрованном виде (gpg + раз в неделю) на отдельный сервер.
- Восстановление инструкция — в `docs/disaster_recovery.md` (создать).

## 7.5 Security headers

В nginx уже есть: `X-Frame-Options DENY`, `X-Content-Type-Options nosniff`, `Strict-Transport-Security`.

Добавить:
```nginx
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), camera=(), microphone=()" always;
add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: https:; script-src 'self' 'unsafe-inline' https://js.sentry-cdn.com; connect-src 'self' https://*.sentry.io https://fonts.googleapis.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com;" always;
add_header Cross-Origin-Opener-Policy "same-origin" always;
```

⚠️ CSP может сломать что-то с фронта — внедрять с `Content-Security-Policy-Report-Only` сначала и смотреть report.

Проверка: https://securityheaders.com/?q=grammy.mediann.dev

## 7.6 PII (Personally Identifiable Information)

В БД хранятся:
- `users.first_name, last_name, username, language_code` — публично в Telegram
- `users.phone, email` — заполняет админ, ПД
- `users.notes` — могут содержать чувствительные данные

Действия:
- Логи: не дампим `notes`, `phone`, `email`, `password_hash`.
- Sentry: `send_default_pii=False` (уже).
- Доступ: только админы с авторизацией.
- Удаление по запросу пользователя (GDPR): `POST /api/users/{id}/anonymize` — обнуляет username/first/last/phone/email/notes (Phase 4).

## 7.7 Чек-лист

- [ ] Миграция `audit_log` + индексы
- [ ] Сервис `emit_audit` и декоратор `@audit`
- [ ] Декоратор применён на все mutating-endpoints
- [ ] UI: страница `/audit` (только super_admin)
- [ ] Миграция: роли в `admins`
- [ ] Декоратор `require_role` + применение
- [ ] CI: bandit, pip-audit, npm audit, Trivy
- [ ] CI: gitleaks
- [ ] Security headers полные
- [ ] CSP в Report-Only, потом в enforcement
- [ ] Документация по ротации секретов
- [ ] Зашифрованный бэкап `.env`
- [ ] Endpoint анонимизации пользователя (GDPR Phase 4)
