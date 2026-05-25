# Funnel Studio — редизайн редактора шагов

Документ описывает редизайн `admin/app/(dash)/funnels/[id]/edit/page.tsx` —
секции «Шаги воронки» (Section 2). Логика и БД сохранены — меняется только
раскладка и компоненты UI. Это первая фаза перед мульти-медиа (Фаза B).

Идеи и часть паттернов заимствованы из проекта `smmplaner` (модель `PostMedia`,
лимиты Bot API, превью-сетки media-group). Их полноценный перенос — отдельные
фазы B и C.

---

## Цели

1. **Расширить рабочую область редактора** — сейчас при 3 равных колонках
   `[1fr · 1.5fr · 1fr]` редактор сжат, многострочный текст и набор кнопок
   едва помещаются.
2. **Сохранить список шагов в зоне видимости** — но дать пользователю
   возможность мгновенно сжать его до узкого рельса, когда список не нужен
   и важна работа с одним шагом.
3. **Сделать список информативнее** — миниатюры медиа, состояние «активен»,
   подсказка задержки.
4. **Превью Telegram всегда видно** — оно главный фидбек-канал, его прятать
   нельзя.

---

## Раскладка

### Развёрнутый список (по умолчанию)

```
┌──────────────┬─────────────────────┬──────────────┐
│              │                     │              │
│   Список     │      Редактор       │   Превью     │
│   шагов      │      шага           │   Telegram   │
│              │                     │              │
│   1fr        │   1.5fr             │   1fr        │
└──────────────┴─────────────────────┴──────────────┘
```

### Свёрнутый список (по клику или ⌘\)

```
┌────┬─────────────────────────────────┬──────────────┐
│ 1  │                                 │              │
│ 2  │        Редактор шага            │   Превью     │
│ 3  │        (больше места)           │   Telegram   │
│ 4  │                                 │              │
│ 56px│        2.5fr                   │   1fr        │
└────┴─────────────────────────────────┴──────────────┘
```

Состояние сохраняется в `localStorage` под ключом
`funnel-studio.steps-list-collapsed`.

### Mobile (`< lg`)

Без изменений — табы `Список / Редактор / Превью`. Это рабочий паттерн,
не трогаем.

---

## Компоненты

### `StepsRail` — узкий рельс свёрнутого списка

- Ширина 56 px.
- Вертикальный стек квадратных кнопок-номеров 40×40 px.
- Активный шаг — gradient indigo→rose background, белая цифра.
- Под цифрой — точка-индикатор медиа, если у шага есть лидмагнит:
  цвет точки кодирует тип (image=teal, video=rose, pdf=amber, document=zinc).
- При hover — `title`-tooltip с превью текста и задержкой.
- Внизу — кнопка-плюс «+» для добавления шага (sm).
- Клик по номеру:
  - Если шаг уже активный — раскрывает список (выходим из рельса).
  - Если другой — переключает active.

### `StepsList` — развёрнутый список (текущий + миниатюры)

К существующим строкам добавляется блок миниатюры медиа слева от номера:
- `photo` → image-thumbnail 40×40 с `object-fit: cover` (после Фазы B —
  превью из `thumbnail_key`; в Фазе A берём preview по `file_url`
  лидмагнита, если он `image`, иначе иконка).
- `video` → чёрный квадрат 40×40 с белой ▶️ по центру.
- `pdf` / `document` → серый квадрат с иконкой `📎`.
- Если медиа нет — компактный кружок-индикатор «текст».

### Кнопка-свёртка

- Маленькая стрелка в правом верхнем углу заголовка списка
  (`⤢ Свернуть` / `⤡ Развернуть`).
- Дублируется хоткеем `⌘\` (на Mac) / `Ctrl+\` (на других ОС).
- Hint в tooltip: «Свернуть список шагов (⌘\)».

### Превью Telegram — без изменений в Фазе A

Получит расширения в Фазе B (media-group рендер).

---

## Поведение

1. По умолчанию список развёрнут (`expanded=true`).
2. Состояние persist в `localStorage`. При первом визите — определяется по
   ширине экрана: `< 1280px` → свёрнут (тесновато), иначе развёрнут.
3. При сворачивании списка редактор плавно расширяется
   (`transition: grid-template-columns 220ms ease`).
4. ⌘\ работает только когда не активен `input` / `textarea` (чтобы не
   ломать ввод).
5. Drag-n-drop порядка шагов работает в обоих режимах. В свёрнутом
   режиме — вертикальный drag на рельсе.

---

## Реализация — конкретно

Файл: `admin/app/(dash)/funnels/[id]/edit/page.tsx`, функция `Section2Steps`.

### State в `Section2Steps`

```ts
const [collapsed, setCollapsed] = useState<boolean>(() => {
  if (typeof window === 'undefined') return false;
  const raw = window.localStorage.getItem('funnel-studio.steps-list-collapsed');
  if (raw === '1') return true;
  if (raw === '0') return false;
  return window.innerWidth < 1280;  // умолчание
});

function toggleCollapsed() {
  setCollapsed((prev) => {
    const next = !prev;
    window.localStorage.setItem('funnel-studio.steps-list-collapsed', next ? '1' : '0');
    return next;
  });
}
```

### Hotkey ⌘\

`useEffect` на window keydown, проверка `(e.metaKey || e.ctrlKey) && e.key === '\\'`,
+ guard: `document.activeElement?.tagName !== 'INPUT' && 'TEXTAREA'`.

### Класс grid

```tsx
<div
  className={clsx(
    'grid grid-cols-1 gap-3 transition-[grid-template-columns] duration-200 ease-in-out',
    collapsed
      ? 'lg:grid-cols-[56px_2.5fr_1fr]'
      : 'lg:grid-cols-[1fr_1.5fr_1fr]',
  )}
>
```

### StepsRail

Новый внутренний компонент рендерится в свёрнутом режиме вместо StepsList.

### Миниатюры

В `StepsList` (развёрнутый режим) добавляется блок до номера шага.
Логика выбора миниатюры — `getStepMediaThumb(step, magnets)`:
- если `lead_magnet_id` указан, и `magnet.file_type === 'image'` и есть
  `file_url` (или присвоенный URL) → image-thumbnail;
- если `'video'` → quadrant `▶️`;
- если `'pdf' | 'document'` → quadrant `📎`;
- иначе мини-индикатор «текст».

В Фазе A `file_url` напрямую не используется (storage локальный, нет
public URL). Используется только иконка по `file_type`. Реальные
превью изображений — в Фазе B.

---

## Что НЕ делаем в Фазе A

- Не трогаем БД.
- Не трогаем API.
- Не меняем `RichTextEditor`.
- Не меняем `TelegramPreview` — пока шлёт 1 файл, рендерит 1 файл.
- Не трогаем backend-worker отправки.
- Не добавляем `funnel_step_media` (отдельная таблица — Фаза B).

---

## Фазы дальше (контекст для будущей работы)

### Фаза B — мульти-медиа на шаг

- Новая таблица `funnel_step_media` с полями по образцу `PostMedia` из
  smmplaner: `storage_key`, `mime_type`, `file_size`, `width`, `height`,
  `duration`, `order_index` (0..19), `caption`, `telegram_file_id`,
  `thumbnail_key`, `checksum_sha256`.
- Endpoint `POST /api/funnel-steps/{id}/media` (multipart), `PATCH .../reorder`,
  `DELETE .../media/{media_id}`.
- Лимиты по образцу smmplaner: 10 MB фото, 50 MB остальное (Bot API),
  2 GiB hard cap загрузки (DB check).
- MIME-детект: `image/jpeg, image/png, image/webp` → photo;
  `video/mp4, video/quicktime, video/webm` → video; `image/gif` → animation;
  `audio/*` → audio; остальное → document.
- Worker `scheduled_messages`: при отправке шага использовать
  `send_media_group` (2-10 медиа), либо корректный одиночный метод
  (`send_photo` / `send_video` / `send_animation` / `send_audio` /
  `send_document`).
- Кэш `telegram_file_id` — после первой отправки.
- Async-задача `generate_step_media_thumbnail` для видео (Pillow + ffmpeg).
- Frontend: компонент `StepMediaPanel` (drag-n-drop, миниатюры с превью,
  reorder, per-item caption, удаление). Превью в Telegram-preview
  расширяется до media-group вида.

### Фаза C — паритет с smmplaner

- Поддержка types: text / single / media-group / poll / audio / voice /
  document / animation. Сейчас в Grammy всё через один text + опц. файл.
- Шар-fallback для файлов > 50 MB (или Local Bot API).
- Custom cover для видео (`cover_storage_key`).
- A/B варианты шага.

---

## Файлы, которые будут изменены в Фазе A

| Файл | Что меняется |
|---|---|
| `admin/app/(dash)/funnels/[id]/edit/page.tsx` | `Section2Steps`: collapsible layout, новый компонент `StepsRail`, миниатюры в `StepsList`, hotkey ⌘\\ |

Один файл. Без бэкенда. Без миграций. Без новых зависимостей.

---

## Acceptance Criteria — Фаза A

- [ ] На экране ≥ 1280 px список развёрнут по умолчанию, занимает ~25%.
- [ ] Кнопка «свернуть» в правом верхнем углу заголовка списка работает.
- [ ] При сворачивании список становится узким 56 px рельсом с номерами шагов
      по вертикали, редактор плавно расширяется.
- [ ] ⌘\\ / Ctrl+\\ переключает свёрнутость, **не работает** когда фокус
      в input/textarea (не ломает ввод).
- [ ] Состояние свёрнутости сохраняется между сессиями (`localStorage`).
- [ ] На экране < 1280 px список свёрнут по умолчанию.
- [ ] В развёрнутом списке у каждой строки шага видна мини-иконка медиа
      (📷/🎬/📎/текст).
- [ ] Mobile (< lg) — табы работают как раньше, кнопка свёртки скрыта.
- [ ] Тайп-чек проходит чисто.

---

## Acceptance Criteria — Фаза B (контекст)

- [ ] Один шаг поддерживает 0..10 медиа.
- [ ] Drag-n-drop загрузка работает.
- [ ] Превью изображений / видео / документов корректное.
- [ ] Reorder drag-and-drop работает.
- [ ] Send в Telegram: media-group для ≥2 файлов, single-media для 1.
- [ ] `telegram_file_id` кэшируется и переиспользуется.
- [ ] Лимиты соблюдаются (10/50 MB Bot API, 2 GiB upload).
- [ ] Миграция: существующие `lead_magnet_id` ссылки → одна запись в
      `funnel_step_media`.
