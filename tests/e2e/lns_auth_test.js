if (!process.env.LNS_TEST_PASSWORD) { console.error('Set LNS_TEST_PASSWORD before running this script.'); process.exit(1); }
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const SCREENSHOT_DIR = '/Users/xxvirusxx/PY/Bots/lns_screenshots';
if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];

  function log(step, status, detail) {
    const msg = `[${status}] Step ${step}: ${detail}`;
    console.log(msg);
    results.push(msg);
  }

  // ── TEST 1: Sign Up Flow ──────────────────────────────────────────────────
  const ctx1 = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page1 = await ctx1.newPage();

  try {
    // Step 1 – Navigate
    await page1.goto('https://lnsbotz.latenightstack.com', { waitUntil: 'networkidle', timeout: 30000 });
    log(1, 'PASS', 'Loaded https://lnsbotz.latenightstack.com');
  } catch (e) {
    log(1, 'FAIL', `Navigation error: ${e.message}`);
    await page1.screenshot({ path: `${SCREENSHOT_DIR}/step1_fail.png`, fullPage: true });
    await browser.close(); process.exit(1);
  }

  try {
    // Step 2 – Click "Get Started"
    const btn = page1.locator('text=Get Started').first();
    await btn.waitFor({ timeout: 10000 });
    await btn.click();
    await page1.waitForTimeout(1000);
    log(2, 'PASS', 'Clicked "Get Started"');
  } catch (e) {
    log(2, 'FAIL', `Could not click Get Started: ${e.message}`);
    await page1.screenshot({ path: `${SCREENSHOT_DIR}/step2_fail.png`, fullPage: true });
  }

  try {
    // Step 3 – Switch to Sign Up tab
    const signUpTab = page1.locator('text=Sign Up').first();
    await signUpTab.waitFor({ timeout: 8000 });
    const isActive = await signUpTab.evaluate(el => el.classList.contains('active') || el.getAttribute('aria-selected') === 'true' || el.getAttribute('data-state') === 'active');
    if (!isActive) await signUpTab.click();
    await page1.waitForTimeout(500);
    log(3, 'PASS', 'On Sign Up tab');
  } catch (e) {
    log(3, 'FAIL', `Sign Up tab issue: ${e.message}`);
  }

  try {
    // Step 4 – Fill form
    const nameField = page1.locator('input[name="name"], input[placeholder*="Name"], input[placeholder*="name"]').first();
    await nameField.waitFor({ timeout: 8000 });
    await nameField.fill('Prabhat Test');

    const emailField = page1.locator('input[type="email"], input[name="email"], input[placeholder*="email"], input[placeholder*="Email"]').first();
    await emailField.fill('prabhat.test2@lnsbotz.ai');

    const pwField = page1.locator('input[type="password"]').first();
    await pwField.fill(process.env.LNS_TEST_PASSWORD);

    log(4, 'PASS', 'Filled Name, Email, Password');
  } catch (e) {
    log(4, 'FAIL', `Form fill error: ${e.message}`);
    await page1.screenshot({ path: `${SCREENSHOT_DIR}/step4_fail.png`, fullPage: true });
  }

  try {
    // Step 5 – Click Create Free Account
    const createBtn = page1.locator('text=Create Free Account').first();
    await createBtn.waitFor({ timeout: 8000 });
    await createBtn.click();
    log(5, 'PASS', 'Clicked "Create Free Account"');
  } catch (e) {
    log(5, 'FAIL', `Could not click Create Free Account: ${e.message}`);
    await page1.screenshot({ path: `${SCREENSHOT_DIR}/step5_fail.png`, fullPage: true });
  }

  // Step 6 – Check for success message or dashboard
  await page1.waitForTimeout(3000);
  const url1After = page1.url();
  const bodyText1 = await page1.evaluate(() => document.body.innerText);
  const hasSuccess = /success|verify|check.*email|dashboard|welcome/i.test(bodyText1);
  const onDashboard = /dashboard/i.test(url1After) || /dashboard/i.test(bodyText1);
  log(6, hasSuccess || onDashboard ? 'PASS' : 'FAIL',
    `URL: ${url1After} | Success msg: ${hasSuccess} | Dashboard: ${onDashboard}`);
  await page1.screenshot({ path: `${SCREENSHOT_DIR}/signup_result.png`, fullPage: true });
  log('6-screenshot', 'PASS', 'Screenshot saved: signup_result.png');

  await ctx1.close();

  // ── TEST 2: Login Flow ────────────────────────────────────────────────────
  const ctx2 = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page2 = await ctx2.newPage();

  try {
    await page2.goto('https://lnsbotz.latenightstack.com', { waitUntil: 'networkidle', timeout: 30000 });
    log(8.1, 'PASS', 'Reloaded site for login test');
  } catch (e) {
    log(8.1, 'FAIL', `Navigation: ${e.message}`);
  }

  try {
    const btn = page2.locator('text=Get Started').first();
    await btn.waitFor({ timeout: 10000 });
    await btn.click();
    await page2.waitForTimeout(800);
    log(8.2, 'PASS', 'Clicked Get Started');
  } catch (e) {
    log(8.2, 'FAIL', `Get Started: ${e.message}`);
  }

  try {
    const loginTab = page2.locator('text=Login, text=Sign In, button:has-text("Login"), [role="tab"]:has-text("Login")').first();
    await loginTab.waitFor({ timeout: 8000 });
    await loginTab.click();
    await page2.waitForTimeout(500);
    log(8.3, 'PASS', 'Clicked Login tab');
  } catch (e) {
    // Try alternative selectors
    try {
      const loginTab2 = page2.getByRole('tab', { name: /login/i });
      await loginTab2.click();
      log(8.3, 'PASS', 'Clicked Login tab (alt selector)');
    } catch (e2) {
      log(8.3, 'FAIL', `Login tab: ${e2.message}`);
    }
  }

  // Step 8 – Fill login credentials
  try {
    const emailField = page2.locator('input[type="email"], input[name="email"], input[placeholder*="email"], input[placeholder*="Email"]').first();
    await emailField.waitFor({ timeout: 8000 });
    await emailField.fill('prabhat@lnsbotz.ai');

    const pwField = page2.locator('input[type="password"]').first();
    await pwField.fill(process.env.LNS_TEST_PASSWORD);

    log(8.4, 'PASS', 'Filled login email + password');
  } catch (e) {
    log(8.4, 'FAIL', `Login form fill: ${e.message}`);
    await page2.screenshot({ path: `${SCREENSHOT_DIR}/login_fill_fail.png`, fullPage: true });
  }

  try {
    const signInBtn = page2.locator('button:has-text("Sign In"), button:has-text("Log In"), button:has-text("Login")').first();
    await signInBtn.waitFor({ timeout: 8000 });
    await signInBtn.click();
    log(8.5, 'PASS', 'Clicked Sign In');
  } catch (e) {
    log(8.5, 'FAIL', `Sign In click: ${e.message}`);
  }

  // Step 9 – Wait and screenshot dashboard
  await page2.waitForTimeout(4000);
  const url2After = page2.url();
  const bodyText2 = await page2.evaluate(() => document.body.innerText);
  const onDashboard2 = /dashboard/i.test(url2After) || /dashboard/i.test(bodyText2);
  const welcomeMsg = (bodyText2.match(/welcome[\s\S]{0,60}/i) || [])[0] || '';
  const planBadge = (bodyText2.match(/(free|pro|starter|enterprise|plan)[\s\S]{0,40}/i) || [])[0] || '';
  const botCount = (bodyText2.match(/\d+\s*(bot|agent)/i) || [])[0] || '';

  log(9, onDashboard2 ? 'PASS' : 'FAIL',
    `URL: ${url2After} | Welcome: "${welcomeMsg.trim()}" | Plan: "${planBadge.trim()}" | Bots: "${botCount}"`);
  await page2.screenshot({ path: `${SCREENSHOT_DIR}/login_dashboard.png`, fullPage: true });
  log('9-screenshot', 'PASS', 'Screenshot saved: login_dashboard.png');

  await ctx2.close();
  await browser.close();

  console.log('\n=== SUMMARY ===');
  results.forEach(r => console.log(r));
})();
