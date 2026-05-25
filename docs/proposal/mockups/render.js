/**
 * Рендерит HTML-мокапы → PNG в docs/proposal/screenshots/, заменяя соответствующие
 * скриншоты «как с прода» на «с боевыми данными».
 */
const path = require('path');
const fs = require('fs');
const { chromium } = require(path.join(__dirname, '..', '..', '..', 'e2e', 'node_modules', 'playwright'));

const MOCKUP_DIR = __dirname;
const OUT_DIR = path.join(__dirname, '..', 'screenshots');

const MAP = {
  'dashboard.html':     '02_dashboard.png',
  'leads.html':         '06_leads.png',
  'subscriptions.html': '08_subscriptions.png',
  'analytics.html':     '13_analytics.png',
};

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await ctx.newPage();
  for (const [html, png] of Object.entries(MAP)) {
    const htmlPath = path.join(MOCKUP_DIR, html);
    const outPath = path.join(OUT_DIR, png);
    await page.goto('file://' + htmlPath, { waitUntil: 'networkidle' });
    // Дать шрифту Inter подгрузиться
    await page.waitForTimeout(400);
    await page.screenshot({ path: outPath, fullPage: false });
    const kb = (fs.statSync(outPath).size / 1024).toFixed(0);
    console.log(`✓ ${png} (${kb} KB)  ←  ${html}`);
  }
  await browser.close();
})();
