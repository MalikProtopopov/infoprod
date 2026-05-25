/**
 * Снимаем скриншоты ключевых экранов админки Grammy для КП и инструкции.
 *
 * Запуск:
 *   node docs/proposal/take_screenshots.js
 *
 * Логинится один раз, сохраняет storageState и проходит по списку URL.
 * Использует Playwright Chromium из e2e/node_modules.
 */
const path = require('path');
const fs = require('fs');

const PLAYWRIGHT_PATH = path.join(__dirname, '..', '..', 'e2e', 'node_modules', 'playwright');
const { chromium } = require(PLAYWRIGHT_PATH);

const BASE_URL = process.env.SCREENSHOT_BASE_URL || 'https://grammy.mediann.dev';
const USERNAME = process.env.ADMIN_USERNAME || 'admin';
const PASSWORD = process.env.ADMIN_PASSWORD;
if (!PASSWORD) {
  console.error('Set ADMIN_PASSWORD env var');
  process.exit(1);
}

const OUT_DIR = path.join(__dirname, 'screenshots');
fs.mkdirSync(OUT_DIR, { recursive: true });

const VIEWPORT = { width: 1440, height: 900 };

// Список экранов для съёмки.
// `wait` — селектор, по которому ждём отрисовки прежде чем щёлкать.
// `full` — сделать ли full-page screenshot вместо viewport.
const PAGES = [
  { name: '01_login',         url: '/login',           wait: 'button:has-text("Войти")', noAuth: true },
  { name: '02_dashboard',     url: '/',                wait: 'aside' },
  { name: '03_products',      url: '/products',        wait: 'aside' },
  { name: '04_channels',      url: '/channels',        wait: 'aside' },
  { name: '05_bots',          url: '/bots',            wait: 'aside' },
  { name: '06_leads',         url: '/leads',           wait: 'aside' },
  { name: '07_payments',      url: '/payments',        wait: 'aside' },
  { name: '08_subscriptions', url: '/subscriptions',   wait: 'aside' },
  { name: '09_funnels_list',  url: '/funnels',         wait: 'aside' },
  { name: '10_lead_magnets',  url: '/lead-magnets',    wait: 'aside' },
  { name: '11_funnel_triggers', url: '/funnel-triggers', wait: 'aside' },
  { name: '12_sources',       url: '/sources',         wait: 'aside' },
  { name: '13_analytics',     url: '/analytics',       wait: 'aside', delay: 1500 },
  { name: '14_users',         url: '/users',           wait: 'aside' },
  { name: '15_audit_log',     url: '/audit-log',       wait: 'aside' },
  { name: '16_account',       url: '/account',         wait: 'aside' },
];

async function snap(page, name, opts = {}) {
  const out = path.join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: out, fullPage: !!opts.full });
  const size = (fs.statSync(out).size / 1024).toFixed(0);
  console.log(`  → ${name}.png (${size} KB)`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    locale: 'ru-RU',
    timezoneId: 'Europe/Moscow',
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();

  // 0) Логин-страница (без auth)
  console.log(`\n[1/${PAGES.length + 2}] login screen`);
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
  await page.waitForSelector('button:has-text("Войти")');
  await snap(page, '01_login');

  // 1) Логин
  console.log(`\n[auth] логинюсь как ${USERNAME}`);
  await page.fill('input[autocomplete="username"]', USERNAME);
  await page.fill('input[autocomplete="current-password"]', PASSWORD);
  await Promise.all([
    page.waitForURL(url => !url.toString().includes('/login'), { timeout: 15000 }),
    page.click('button:has-text("Войти")'),
  ]);
  console.log('  ✓ авторизован');

  // 2) Проходим по списку с авторизацией
  for (let i = 1; i < PAGES.length; i++) {
    const p = PAGES[i];
    console.log(`\n[${i + 2}/${PAGES.length + 2}] ${p.name}: ${p.url}`);
    try {
      await page.goto(`${BASE_URL}${p.url}`, { waitUntil: 'networkidle', timeout: 20000 });
      if (p.wait) await page.waitForSelector(p.wait, { timeout: 8000 });
      if (p.delay) await page.waitForTimeout(p.delay);
      await snap(page, p.name);
    } catch (e) {
      console.log(`  ✗ ${p.name} skipped: ${e.message.split('\n')[0]}`);
    }
  }

  // 3) Бонусом — Студия воронки (первой попавшейся)
  try {
    console.log(`\n[bonus] Студия воронок`);
    await page.goto(`${BASE_URL}/funnels`, { waitUntil: 'networkidle' });
    const studioLinks = await page.$$eval('a[href*="/funnels/"][href*="/edit"]', els =>
      els.map(e => e.getAttribute('href')).filter(h => /\/funnels\/\d+\/edit/.test(h))
    );
    if (studioLinks.length > 0) {
      await page.goto(`${BASE_URL}${studioLinks[0]}`, { waitUntil: 'networkidle', timeout: 25000 });
      await page.waitForTimeout(1500);
      await snap(page, '17_funnel_studio');

      // Прокрутить и сделать ещё один скрин — секция «Шаги»
      await page.evaluate(() => window.scrollBy(0, 600));
      await page.waitForTimeout(800);
      await snap(page, '18_funnel_studio_steps');

      // Прокрутить ещё — секция «Точки входа»
      await page.evaluate(() => window.scrollBy(0, 800));
      await page.waitForTimeout(800);
      await snap(page, '19_funnel_studio_entry_points');
    } else {
      console.log('  (нет воронок для съёмки)');
    }
  } catch (e) {
    console.log(`  ✗ studio skipped: ${e.message.split('\n')[0]}`);
  }

  // 4) Мобильный вид (для гайда)
  try {
    console.log(`\n[mobile] mobile sidebar`);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    await snap(page, '20_mobile_dashboard');
    // Открыть бургер
    const burger = await page.$('button[aria-label*="меню"], button[aria-label="Открыть меню"]');
    if (burger) {
      await burger.click();
      await page.waitForTimeout(300);
      await snap(page, '21_mobile_sidebar');
    }
  } catch (e) {
    console.log(`  ✗ mobile skipped: ${e.message.split('\n')[0]}`);
  }

  await browser.close();
  console.log('\n✓ Все скриншоты сохранены в', OUT_DIR);
})();
