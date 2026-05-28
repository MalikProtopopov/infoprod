import { describe, expect, it } from 'vitest';

import { fromEditorHtml, toEditorHtml } from '@/lib/telegramHtml';

describe('telegramHtml: fromEditorHtml (DOM → Telegram HTML)', () => {
  it('keeps basic inline tags', () => {
    expect(fromEditorHtml('<b>bold</b>')).toBe('<b>bold</b>');
    expect(fromEditorHtml('<i>it</i>')).toBe('<i>it</i>');
    expect(fromEditorHtml('<u>u</u>')).toBe('<u>u</u>');
    expect(fromEditorHtml('<s>s</s>')).toBe('<s>s</s>');
  });

  it('normalizes synonym tags to Telegram set', () => {
    expect(fromEditorHtml('<strong>x</strong>')).toBe('<b>x</b>');
    expect(fromEditorHtml('<em>x</em>')).toBe('<i>x</i>');
    expect(fromEditorHtml('<strike>x</strike>')).toBe('<s>x</s>');
    expect(fromEditorHtml('<del>x</del>')).toBe('<s>x</s>');
    expect(fromEditorHtml('<ins>x</ins>')).toBe('<u>x</u>');
  });

  it('converts style-spans (execCommand/paste) to tags', () => {
    expect(fromEditorHtml('<span style="font-weight: bold">x</span>')).toBe('<b>x</b>');
    expect(fromEditorHtml('<span style="font-weight: 700">x</span>')).toBe('<b>x</b>');
    expect(fromEditorHtml('<span style="font-style: italic">x</span>')).toBe('<i>x</i>');
    expect(fromEditorHtml('<span style="text-decoration: line-through">x</span>')).toBe('<s>x</s>');
  });

  it('handles code and pre', () => {
    expect(fromEditorHtml('<code>c</code>')).toBe('<code>c</code>');
    expect(fromEditorHtml('<pre>block</pre>')).toBe('<pre>block</pre>');
  });

  it('handles blockquote and expandable blockquote', () => {
    expect(fromEditorHtml('<blockquote>q</blockquote>')).toBe('<blockquote>q</blockquote>');
    expect(fromEditorHtml('<blockquote expandable>q</blockquote>')).toBe('<blockquote expandable>q</blockquote>');
  });

  it('handles spoiler element and span.tg-spoiler', () => {
    expect(fromEditorHtml('<tg-spoiler>s</tg-spoiler>')).toBe('<tg-spoiler>s</tg-spoiler>');
    expect(fromEditorHtml('<span class="tg-spoiler">s</span>')).toBe('<tg-spoiler>s</tg-spoiler>');
  });

  it('handles links with href', () => {
    expect(fromEditorHtml('<a href="https://e.com">go</a>')).toBe('<a href="https://e.com">go</a>');
  });

  it('converts <br> to newline', () => {
    expect(fromEditorHtml('a<br>b')).toBe('a\nb');
  });

  it('separates div/p blocks with newline', () => {
    expect(fromEditorHtml('<div>a</div><div>b</div>')).toBe('a\nb');
    expect(fromEditorHtml('a<div>b</div>')).toBe('a\nb');
  });

  it('escapes special chars in text', () => {
    expect(fromEditorHtml('a &lt; b &amp; c')).toBe('a &lt; b &amp; c');
  });

  it('keeps nested formatting', () => {
    expect(fromEditorHtml('<blockquote>see <b>this</b></blockquote>'))
      .toBe('<blockquote>see <b>this</b></blockquote>');
  });

  it('drops empty formatting wrappers', () => {
    expect(fromEditorHtml('<b></b>')).toBe('');
  });

  it('collapses 3+ newlines to double', () => {
    expect(fromEditorHtml('a<br><br><br><br>b')).toBe('a\n\nb');
  });
});

describe('telegramHtml: toEditorHtml (Telegram HTML → editor DOM html)', () => {
  it('converts newlines to <br>', () => {
    expect(toEditorHtml('a\nb')).toBe('a<br>b');
    expect(toEditorHtml('<b>x</b>\ny')).toBe('<b>x</b><br>y');
  });

  it('empty stays empty', () => {
    expect(toEditorHtml('')).toBe('');
  });
});

describe('telegramHtml: round-trip', () => {
  const cases = [
    '<b>bold</b> and <i>italic</i>',
    'line1\nline2',
    '<blockquote expandable>hidden details</blockquote>',
    'intro\n<tg-spoiler>secret</tg-spoiler>\noutro',
    '<a href="https://t.me/x">link</a>',
  ];
  for (const tg of cases) {
    it(`round-trips: ${JSON.stringify(tg)}`, () => {
      expect(fromEditorHtml(toEditorHtml(tg))).toBe(tg);
    });
  }
});
