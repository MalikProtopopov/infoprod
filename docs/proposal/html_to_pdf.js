/**
 * Конвертер HTML → PDF через Playwright Chromium.
 *
 * Запуск:
 *   node html_to_pdf.js <input.html> <output.pdf> [--landscape] [--guide]
 *
 * Флаг --guide включает Chromium-level header/footer с авто-нумерацией страниц.
 * Применяется к Grammy_Guide.pdf — там длинные главы могут переходить на 2-ю
 * страницу, и нужно повторять колонтитулы.
 */
const path = require('path');
const fs = require('fs');
const { chromium } = require(path.join(__dirname, '..', '..', 'e2e', 'node_modules', 'playwright'));

// Колонтитулы для гайда — рендерятся Chromium-ом на каждой физической странице.
// Не рендерятся на странице с классом `.no-chrome` (это cover).
const GUIDE_HEADER = `
<div style="width:100%; padding: 6mm 18mm 0; font-family: -apple-system, BlinkMacSystemFont, Helvetica, sans-serif;
            font-size: 8.5pt; color: #9ca3af; display: flex; justify-content: space-between;
            border-bottom: 1px solid #f3f4f6; padding-bottom: 3mm;">
  <div style="color: #6366f1; font-weight: 700; letter-spacing: 1.5px;">GRAMMY</div>
  <div>Руководство пользователя</div>
</div>`;

const GUIDE_FOOTER = `
<div style="width:100%; padding: 0 18mm 6mm; font-family: -apple-system, BlinkMacSystemFont, Helvetica, sans-serif;
            font-size: 8.5pt; color: #9ca3af; display: flex; justify-content: space-between;
            border-top: 1px solid #f3f4f6; padding-top: 3mm;">
  <div>mediann.dev · 2026</div>
  <div><span class="pageNumber"></span> / <span class="totalPages"></span></div>
</div>`;

(async () => {
  const inHtml = path.resolve(process.argv[2]);
  const outPdf = path.resolve(process.argv[3]);
  const landscape = process.argv.includes('--landscape');
  const isGuide = process.argv.includes('--guide');

  if (!fs.existsSync(inHtml)) {
    console.error('No such file:', inHtml);
    process.exit(1);
  }

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + inHtml, { waitUntil: 'networkidle' });
  await page.emulateMedia({ media: 'print' });

  const pdfOpts = {
    path: outPdf,
    format: 'A4',
    landscape,
    printBackground: true,
    margin: { top: 0, right: 0, bottom: 0, left: 0 },
  };

  if (isGuide) {
    pdfOpts.margin = { top: '22mm', right: 0, bottom: '18mm', left: 0 };
    pdfOpts.displayHeaderFooter = true;
    pdfOpts.headerTemplate = GUIDE_HEADER;
    pdfOpts.footerTemplate = GUIDE_FOOTER;
  }

  await page.pdf(pdfOpts);
  await browser.close();
  const kb = (fs.statSync(outPdf).size / 1024).toFixed(0);
  console.log(`✓ PDF: ${outPdf} (${kb} KB)`);
})();
