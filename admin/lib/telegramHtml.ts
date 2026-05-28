/**
 * Двусторонняя конвертация между Telegram parse_mode=HTML и DOM
 * contentEditable-редактора (RichTextEditor).
 *
 * Контракт RichTextEditor.value — строка Telegram-HTML (её хранит бэкенд и
 * отправляет ботом). Редактор показывает её как форматированный текст, а на
 * правках сериализует обратно в Telegram-HTML.
 *
 * Поддержанные теги: b/strong, i/em, u/ins, s/strike/del, code, pre,
 * blockquote (+ expandable), tg-spoiler (+ span.tg-spoiler), a[href].
 * Переводы строк: \n ↔ <br>.
 */

const BLOCK_TAGS = new Set(['div', 'p']);

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Telegram-HTML → HTML для отображения в contentEditable (\n → <br>). */
export function toEditorHtml(tg: string): string {
  if (!tg) return '';
  return tg.replace(/\r\n?/g, '\n').replace(/\n/g, '<br>');
}

function wrapTag(tag: string, inner: string): string {
  return inner ? `<${tag}>${inner}</${tag}>` : '';
}

function spanToTelegram(el: HTMLElement, inner: string): string {
  if (!inner) return '';
  const style = (el.getAttribute('style') || '').toLowerCase();
  const cls = el.className || '';
  let open = '';
  let close = '';
  const add = (o: string, c: string) => { open += o; close = c + close; };
  if (/font-weight:\s*(bold|[6-9]\d\d)/.test(style)) add('<b>', '</b>');
  if (/font-style:\s*italic/.test(style)) add('<i>', '</i>');
  if (/text-decoration[^;]*underline/.test(style)) add('<u>', '</u>');
  if (/text-decoration[^;]*line-through/.test(style)) add('<s>', '</s>');
  if (cls.includes('tg-spoiler')) add('<tg-spoiler>', '</tg-spoiler>');
  return `${open}${inner}${close}`;
}

function serializeNode(node: Node): string {
  if (node.nodeType === 3) return esc(node.nodeValue || '');
  if (node.nodeType !== 1) return '';
  const el = node as HTMLElement;
  const tag = el.tagName.toLowerCase();
  if (tag === 'br') return '\n';
  const inner = serializeChildren(el);
  switch (tag) {
    case 'b': case 'strong': return wrapTag('b', inner);
    case 'i': case 'em': return wrapTag('i', inner);
    case 'u': case 'ins': return wrapTag('u', inner);
    case 's': case 'strike': case 'del': return wrapTag('s', inner);
    case 'code': return wrapTag('code', inner);
    case 'pre': return wrapTag('pre', inner);
    case 'tg-spoiler': return wrapTag('tg-spoiler', inner);
    case 'blockquote': {
      if (!inner) return '';
      const exp = el.hasAttribute('expandable') || el.getAttribute('data-expandable') === 'true';
      return `<blockquote${exp ? ' expandable' : ''}>${inner}</blockquote>`;
    }
    case 'a': {
      const href = (el.getAttribute('href') || '').replace(/"/g, '&quot;');
      return inner && href ? `<a href="${href}">${inner}</a>` : inner;
    }
    case 'span':
      return spanToTelegram(el, inner);
    default:
      // div/p/прочее — просто содержимое; разделение блоков делает serializeChildren.
      return inner;
  }
}

function serializeChildren(node: Node): string {
  let out = '';
  node.childNodes.forEach((child) => {
    const isBlock =
      child.nodeType === 1 && BLOCK_TAGS.has((child as HTMLElement).tagName.toLowerCase());
    // Блочный элемент (div/p из contentEditable) = перенос строки от предыдущего.
    if (isBlock && out && !out.endsWith('\n')) out += '\n';
    out += serializeNode(child);
  });
  return out;
}

/** DOM contentEditable → Telegram-HTML. */
export function fromEditorDom(root: HTMLElement): string {
  const out = serializeChildren(root);
  // contentEditable плодит лишние переносы — схлопываем 3+ в двойной.
  return out.replace(/\n{3,}/g, '\n\n');
}

/** Хелпер для тестов/SSR: HTML-строка → Telegram-HTML (через временный div). */
export function fromEditorHtml(html: string): string {
  if (typeof document === 'undefined') return html;
  const div = document.createElement('div');
  div.innerHTML = html;
  return fromEditorDom(div);
}
