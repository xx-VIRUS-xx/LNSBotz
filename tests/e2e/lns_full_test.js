if (!process.env.LNS_TEST_PASSWORD) { console.error('Set LNS_TEST_PASSWORD before running this script.'); process.exit(1); }
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOTS_DIR = '/Users/xxvirusxx/PY/Bots/lns_screenshots';
if (!fs.existsSync(SCREENSHOTS_DIR)) fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

const consoleErrors = [];
const networkRequests = {};

async function shot(page, name) {
  const p = path.join(SCREENSHOTS_DIR, `${name}.png`);
  await page.screenshot({ path: p, fullPage: false });
  console.log(`[SCREENSHOT] ${p}`);
}

async function getConsoleErrors() {
  const errs = [...consoleErrors];
  consoleErrors.length = 0;
  return errs;
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  const page = await context.newPage();

  // Capture all console messages
  page.on('console', msg => {
    const type = msg.type();
    if (type === 'error' || type === 'warn') {
      consoleErrors.push({ type, text: msg.text(), location: msg.location() });
    }
  });

  // Capture page errors
  page.on('pageerror', err => {
    consoleErrors.push({ type: 'pageerror', text: err.message, stack: err.stack });
  });

  // Capture network responses
  page.on('response', async response => {
    const url = response.url();
    const status = response.status();
    if (url.includes('/api/') || url.includes('supabase') || url.includes('auth') || url.includes('run') || url.includes('generate') || url.includes('lnsbotz')) {
      let body = '';
      try {
        body = await response.text();
        if (body.length > 2000) body = body.substring(0, 2000) + '...[truncated]';
      } catch(e) { body = '[could not read body]'; }
      networkRequests[url] = { status, body, method: response.request().method() };
    }
  });

  // ─── STEP 1: Open homepage ──────────────────────────────────────────────────
  console.log('\n========== STEP 1: Opening homepage ==========');
  await page.goto('https://lnsbotz.latenightstack.com', { waitUntil: 'networkidle', timeout: 30000 });
  await sleep(2000);
  await shot(page, '01_homepage');

  const title = await page.title();
  console.log(`[TITLE] ${title}`);

  const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 500));
  console.log(`[BODY TEXT PREVIEW] ${bodyText}`);

  let errs = await getConsoleErrors();
  if (errs.length) {
    console.log('[CONSOLE ERRORS/WARNINGS after homepage load]');
    errs.forEach(e => console.log(`  [${e.type}] ${e.text}`));
  } else {
    console.log('[CONSOLE] No errors on homepage load');
  }

  // ─── STEP 2: Click "Get Started" ────────────────────────────────────────────
  console.log('\n========== STEP 2: Clicking "Get Started" ==========');
  const getStartedBtn = await page.$('text=Get Started');
  if (getStartedBtn) {
    console.log('[FOUND] "Get Started" button');
    await getStartedBtn.click();
    await sleep(1500);
    await shot(page, '02_after_get_started_click');

    // Check if modal opened
    const modalVisible = await page.evaluate(() => {
      const els = document.querySelectorAll('[role="dialog"], .modal, [class*="modal"], [class*="Modal"], [id*="modal"], [id*="Modal"]');
      return Array.from(els).filter(el => {
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      }).map(el => ({ tag: el.tagName, class: el.className, id: el.id }));
    });
    if (modalVisible.length) {
      console.log('[MODAL OPENED]', JSON.stringify(modalVisible));
    } else {
      console.log('[MODAL] No modal detected via role/class - checking visible content change...');
      const url = page.url();
      console.log(`[URL after click] ${url}`);
    }
  } else {
    console.log('[NOT FOUND] No "Get Started" button found on page');
    // List all buttons
    const buttons = await page.$$eval('button, a[href]', els => els.slice(0, 20).map(el => ({ text: el.innerText?.trim(), href: el.href, class: el.className })));
    console.log('[BUTTONS/LINKS on page]', JSON.stringify(buttons, null, 2));
  }

  errs = await getConsoleErrors();
  if (errs.length) {
    console.log('[CONSOLE ERRORS after Get Started click]');
    errs.forEach(e => console.log(`  [${e.type}] ${e.text}`));
  } else {
    console.log('[CONSOLE] No errors after Get Started click');
  }

  // ─── STEP 3: Login ──────────────────────────────────────────────────────────
  console.log('\n========== STEP 3: Login with email/password ==========');

  // Find email input
  const emailInput = await page.$('input[type="email"], input[name="email"], input[placeholder*="email" i], input[placeholder*="Email" i]');
  if (emailInput) {
    console.log('[FOUND] Email input field');
    await emailInput.fill('prabhat@lnsbotz.ai');
  } else {
    console.log('[NOT FOUND] Email input - trying to navigate to login page...');
    // Try navigating to /login or /auth/login
    for (const loginPath of ['/login', '/auth/login', '/signin', '/auth/signin', '/auth']) {
      try {
        await page.goto(`https://lnsbotz.latenightstack.com${loginPath}`, { waitUntil: 'networkidle', timeout: 15000 });
        await sleep(1000);
        const inp = await page.$('input[type="email"], input[name="email"]');
        if (inp) {
          console.log(`[FOUND] Login page at ${loginPath}`);
          await inp.fill('prabhat@lnsbotz.ai');
          break;
        }
      } catch(e) { /* continue */ }
    }
  }

  await shot(page, '03a_login_form');

  const passwordInput = await page.$('input[type="password"]');
  if (passwordInput) {
    console.log('[FOUND] Password input field');
    await passwordInput.fill(process.env.LNS_TEST_PASSWORD);
  } else {
    console.log('[NOT FOUND] Password input field');
  }

  await shot(page, '03b_login_filled');

  // Click Sign In button
  const signInBtn = await page.$('button[type="submit"], button:has-text("Sign In"), button:has-text("Login"), button:has-text("Log In"), button:has-text("Continue")');
  if (signInBtn) {
    const btnText = await signInBtn.evaluate(el => el.innerText);
    console.log(`[FOUND] Sign in button: "${btnText.trim()}"`);

    // Capture network before click
    const networkBefore = Object.keys(networkRequests).length;

    await signInBtn.click();
    await sleep(3000); // wait for auth to complete

    await shot(page, '03c_after_signin_click');

    const urlAfterLogin = page.url();
    console.log(`[URL after sign in] ${urlAfterLogin}`);

    // Check for error messages
    const errorMessages = await page.evaluate(() => {
      const errorEls = document.querySelectorAll('[class*="error" i], [class*="alert" i], [role="alert"], .text-red-500, .text-red-600, [class*="danger"]');
      return Array.from(errorEls).map(el => el.innerText?.trim()).filter(t => t);
    });
    if (errorMessages.length) {
      console.log('[ERROR MESSAGES on page]', errorMessages);
    } else {
      console.log('[NO visible error messages after sign in]');
    }

    // Print network requests captured during login
    const networkAfter = Object.keys(networkRequests);
    console.log('[NETWORK REQUESTS captured during/after login]');
    networkAfter.forEach(url => {
      const r = networkRequests[url];
      console.log(`  [${r.method}] ${url} -> STATUS: ${r.status}`);
      if (r.body && r.body !== '[could not read body]') {
        console.log(`  BODY: ${r.body.substring(0, 500)}`);
      }
    });
  } else {
    console.log('[NOT FOUND] No Sign In button found');
    const allButtons = await page.$$eval('button', els => els.map(el => el.innerText?.trim()));
    console.log('[ALL BUTTONS]', allButtons);
  }

  errs = await getConsoleErrors();
  if (errs.length) {
    console.log('[CONSOLE ERRORS after login attempt]');
    errs.forEach(e => console.log(`  [${e.type}] ${e.text}`));
  } else {
    console.log('[CONSOLE] No errors after login attempt');
  }

  // ─── STEP 4: Check nav after login ──────────────────────────────────────────
  console.log('\n========== STEP 4: Nav after login ==========');
  await sleep(2000);
  await shot(page, '04_nav_after_login');

  const navContent = await page.evaluate(() => {
    const nav = document.querySelector('nav, header, [class*="nav" i], [class*="header" i], [class*="sidebar" i]');
    return nav ? nav.innerText?.trim().substring(0, 300) : 'NO NAV FOUND';
  });
  console.log(`[NAV CONTENT] ${navContent}`);

  const currentUrl = page.url();
  console.log(`[CURRENT URL] ${currentUrl}`);

  // ─── STEP 5: Scroll down ─────────────────────────────────────────────────────
  console.log('\n========== STEP 5: Scroll down for dashboard ==========');
  await page.evaluate(() => window.scrollBy(0, 600));
  await sleep(1000);
  await shot(page, '05_scrolled_down');

  const dashboardVisible = await page.evaluate(() => {
    const els = document.querySelectorAll('[class*="dashboard" i], [class*="product" i], [class*="card" i], main');
    return Array.from(els).slice(0, 5).map(el => ({ class: el.className, text: el.innerText?.trim().substring(0, 100) }));
  });
  console.log('[DASHBOARD ELEMENTS]', JSON.stringify(dashboardVisible, null, 2));

  errs = await getConsoleErrors();
  if (errs.length) {
    console.log('[CONSOLE ERRORS after scroll]');
    errs.forEach(e => console.log(`  [${e.type}] ${e.text}`));
  }

  // ─── STEP 6: Click "Legal Notice" product card ────────────────────────────
  console.log('\n========== STEP 6: Click Legal Notice product card ==========');
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(500);

  const legalNoticeCard = await page.$('text=Legal Notice');
  if (legalNoticeCard) {
    console.log('[FOUND] Legal Notice card/element');
    await legalNoticeCard.click();
    await sleep(2000);
    await shot(page, '06_after_legal_notice_click');

    const panelVisible = await page.evaluate(() => {
      const els = document.querySelectorAll('[class*="panel" i], [class*="drawer" i], [class*="sidebar" i], [class*="modal" i], [role="dialog"]');
      return Array.from(els).filter(el => {
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden';
      }).map(el => ({ class: el.className.substring(0, 80), text: el.innerText?.trim().substring(0, 100) }));
    });
    console.log('[PANEL ELEMENTS]', JSON.stringify(panelVisible, null, 2));
  } else {
    console.log('[NOT FOUND] No "Legal Notice" element on page');
    // Find all clickable cards
    const cards = await page.$$eval('[class*="card" i], [class*="product" i]', els =>
      els.slice(0, 10).map(el => ({ class: el.className.substring(0,60), text: el.innerText?.trim().substring(0,80) }))
    );
    console.log('[AVAILABLE CARDS]', JSON.stringify(cards, null, 2));
  }

  errs = await getConsoleErrors();
  if (errs.length) {
    console.log('[CONSOLE ERRORS after Legal Notice click]');
    errs.forEach(e => console.log(`  [${e.type}] ${e.text}`));
  }

  // ─── STEP 7: Type in textarea and click Run ──────────────────────────────
  console.log('\n========== STEP 7: Type in textarea and click Run ==========');
  const textarea = await page.$('textarea, [contenteditable="true"], input[type="text"][class*="prompt" i]');
  if (textarea) {
    console.log('[FOUND] Textarea/input');
    await textarea.fill('You owe Rs 50000. Pay in 15 days or face court action.');
    await sleep(500);
    await shot(page, '07a_textarea_filled');

    // Clear previous network requests and track new ones
    Object.keys(networkRequests).forEach(k => delete networkRequests[k]);

    const runBtn = await page.$('button:has-text("Run"), button:has-text("Generate"), button:has-text("Submit"), button:has-text("Send"), button[type="submit"]');
    if (runBtn) {
      const runBtnText = await runBtn.evaluate(el => el.innerText);
      console.log(`[FOUND] Run button: "${runBtnText.trim()}"`);
      await runBtn.click();
      await sleep(5000); // wait for API response

      await shot(page, '07b_after_run_click');

      // Check result
      const resultContent = await page.evaluate(() => {
        const result = document.querySelector('[class*="result" i], [class*="output" i], [class*="response" i], [class*="generated" i]');
        return result ? result.innerText?.trim().substring(0, 500) : null;
      });
      console.log(`[RESULT CONTENT] ${resultContent || 'No result element found'}`);

      console.log('\n[NETWORK REQUESTS during Run]');
      Object.keys(networkRequests).forEach(url => {
        const r = networkRequests[url];
        console.log(`  [${r.method}] ${url}`);
        console.log(`  STATUS: ${r.status}`);
        console.log(`  BODY: ${r.body?.substring(0, 1000)}`);
        console.log('  ---');
      });

    } else {
      console.log('[NOT FOUND] No Run/Generate/Submit button');
      const allBtns = await page.$$eval('button', els => els.map(el => el.innerText?.trim()).filter(t => t));
      console.log('[ALL BUTTONS]', allBtns);
    }
  } else {
    console.log('[NOT FOUND] No textarea on page - checking current page state');
    const currentPageText = await page.evaluate(() => document.body.innerText.substring(0, 600));
    console.log('[PAGE TEXT]', currentPageText);
    await shot(page, '07_no_textarea');
  }

  errs = await getConsoleErrors();
  if (errs.length) {
    console.log('[CONSOLE ERRORS after Run]');
    errs.forEach(e => console.log(`  [${e.type}] ${e.text}`));
  } else {
    console.log('[CONSOLE] No errors after Run');
  }

  // ─── STEP 8: Full console error dump ─────────────────────────────────────
  console.log('\n========== STEP 8: All remaining console errors ==========');
  errs = await getConsoleErrors();
  if (errs.length) {
    errs.forEach(e => console.log(`  [${e.type}] ${e.text}`));
  } else {
    console.log('[CONSOLE] No additional errors');
  }

  // ─── STEP 10: Try "Continue with Google" ──────────────────────────────────
  console.log('\n========== STEP 10: Try "Continue with Google" ==========');
  // Go back to login
  await page.goto('https://lnsbotz.latenightstack.com', { waitUntil: 'networkidle', timeout: 20000 });
  await sleep(1500);

  const getStartedBtn2 = await page.$('text=Get Started');
  if (getStartedBtn2) {
    await getStartedBtn2.click();
    await sleep(1500);
  }

  const googleBtn = await page.$('text=Continue with Google, button:has-text("Google"), a:has-text("Google")');
  if (googleBtn) {
    console.log('[FOUND] "Continue with Google" button');
    await shot(page, '10a_before_google_click');
    await googleBtn.click();
    await sleep(3000);
    await shot(page, '10b_after_google_click');
    const urlAfterGoogle = page.url();
    console.log(`[URL after Google click] ${urlAfterGoogle}`);
  } else {
    console.log('[NOT FOUND] No "Continue with Google" button');
    await shot(page, '10_no_google_btn');
    // Check what auth options are available
    const authOptions = await page.evaluate(() => {
      return document.body.innerText.substring(0, 800);
    });
    console.log('[PAGE CONTENT]', authOptions);
  }

  errs = await getConsoleErrors();
  if (errs.length) {
    console.log('[CONSOLE ERRORS after Google click]');
    errs.forEach(e => console.log(`  [${e.type}] ${e.text}`));
  }

  // Final network summary
  console.log('\n========== FINAL NETWORK SUMMARY ==========');
  Object.keys(networkRequests).forEach(url => {
    const r = networkRequests[url];
    console.log(`[${r.method}] ${url} -> ${r.status}`);
  });

  await browser.close();
  console.log('\n[DONE] Test complete. Screenshots in:', SCREENSHOTS_DIR);
})();
