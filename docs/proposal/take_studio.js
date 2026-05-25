const path = require('path');
const fs = require('fs');
const { chromium } = require(path.join(__dirname, '..', '..', 'e2e', 'node_modules', 'playwright'));

const BASE_URL = 'https://grammy.mediann.dev';
const OUT_DIR = path.join(__dirname, 'screenshots');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: 'ru-RU',
    ignoreHTTPSErrors: true,
  });
  const page = await ctx.newPage();

  // login
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[autocomplete="username"]', process.env.ADMIN_USERNAME);
  await page.fill('input[autocomplete="current-password"]', process.env.ADMIN_PASSWORD);
  await Promise.all([
    page.waitForURL(u => !u.toString().includes('/login')),
    page.click('button:has-text("Войти")'),
  ]);

  // Студия — без networkidle (там SWR постоянно дёргает)
  await page.goto(`${BASE_URL}/funnels`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);
  const links = await page.$$eval('a[href*="/funnels/"][href*="/edit"]',
    els => els.map(e => e.getAttribute('href')).filter(h => /\/funnels\/\d+\/edit/.test(h)));

  if (links.length === 0) {
    console.log('Нет воронок для съёмки');
    await browser.close();
    process.exit(0);
  }

  console.log(`Открываю ${links[0]}`);
  await page.goto(`${BASE_URL}${links[0]}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(OUT_DIR, '17_funnel_studio.png') });
  console.log('  ✓ 17_funnel_studio');

  await page.evaluate(() => window.scrollBy(0, 700));
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT_DIR, '18_funnel_studio_steps.png') });
  console.log('  ✓ 18_funnel_studio_steps');

  await page.evaluate(() => window.scrollBy(0, 900));
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT_DIR, '19_funnel_studio_entry_points.png') });
  console.log('  ✓ 19_funnel_studio_entry_points');

  await page.evaluate(() => window.scrollBy(0, 900));
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT_DIR, '22_funnel_studio_launch.png') });
  console.log('  ✓ 22_funnel_studio_launch');

  await browser.close();
})();
