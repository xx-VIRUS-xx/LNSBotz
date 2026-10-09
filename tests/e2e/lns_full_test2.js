if (!process.env.LNS_TEST_PASSWORD) { console.error('Set LNS_TEST_PASSWORD before running this script.'); process.exit(1); }
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOTS_DIR = '/Users/xxvirusxx/PY/Bots/lns_screenshots';
if (!fs.existsSync(SCREENSHOTS_DIR)) fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

const consoleErrors = [];
const networkRequests = {};
const allNetworkRequests = [];

async function shot(page, name) {
  const p = path.join(SCREENSHOTS_DIR, `${name}.png`);
  await page.screenshot({ path: p, fullPage: false });
  console.log(`[SCREENSHOT] ${p}`);
}

function flushErrors() {
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
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
  });
  const page = await context.newPage();

  // Capture all console messages
  page.on('console', msg => {
    const type = msg.type();
    consoleErrors.push({ type, text: msg.text(), location: msg.location() });
  });
  page.on('pageerror', err => {
    consoleErrors.push({ type: 'pageerror', text: err.message, stack: err.stack });
  });

  // Capture ALL network
  page.on('response', async response => {
    const url = response.url();
    const status = response.status();
    if (url.includes('/api/') || url.includes('supabase') || url.includes('auth') ||
        url.includes('run') || url.includes('generate') || url.includes('lnsbotz') ||
        url.includes('googleapis') || url.includes('google') || url.includes('token')) {
      let body = '';
      try {
        body = await response.text();
        if (body.length > 3000) body = body.substring(0, 3000) + '...[truncated]';
      } catch(e) { body = '[could not read body]'; }
      const entry = { url, status, body, method: response.request().method(), time: new Date().toISOString() };
      networkRequests[url] = entry;
      allNetworkRequests.push(entry);
    }
  });

  // ─── STEP 1: Open homepage ──────────────────────────────────────────────────
  console.log('\n==============================');
  console.log('STEP 1: Opening homepage');
  console.log('==============================');
  await page.goto('https://lnsbotz.latenightstack.com', { waitUntil: 'networkidle', timeout: 30000 });
  await sleep(2000);
  await shot(page, '01_homepage');

  const title = await page.title();
  console.log(`TITLE: ${title}`);
  console.log(`URL: ${page.url()}`);

  const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 600));
  console.log(`BODY TEXT PREVIEW:\n${bodyText}`);

  let errs = flushErrors();
  console.log(`\nCONSOLE ERRORS (${errs.filter(e=>e.type==='error'||e.type==='pageerror').length} errors, ${errs.filter(e=>e.type==='warn').length} warnings):`);
  errs.filter(e => e.type === 'error' || e.type === 'pageerror' || e.type === 'warn').forEach(e =>
    console.log(`  [${e.type.toUpperCase()}] ${e.text}`)
  );

  // ─── STEP 2: Click "Get Started" ────────────────────────────────────────────
  console.log('\n==============================');
  console.log('STEP 2: Click "Get Started"');
  console.log('==============================');

  const getStartedBtn = await page.$('a:has-text("Get Started"), button:has-text("Get Started")');
  if (getStartedBtn) {
    await getStartedBtn.click();
    await sleep(2000);
    console.log('Clicked "Get Started"');
  } else {
    console.log('ERROR: "Get Started" button not found!');
  }

  await shot(page, '02_after_get_started_click');
  console.log(`URL after click: ${page.url()}`);

  // Inspect modal DOM
  const modalInfo = await page.evaluate(() => {
    const modal = document.querySelector('.modal, [role="dialog"], [id*="modal"]');
    if (!modal) return { found: false };
    const style = window.getComputedStyle(modal);
    const inputs = modal.querySelectorAll('input, button, a');
    return {
      found: true,
      class: modal.className,
      id: modal.id,
      display: style.display,
      visibility: style.visibility,
      opacity: style.opacity,
      transform: style.transform,
      innerHTML: modal.innerHTML.substring(0, 2000),
      inputs: Array.from(inputs).map(el => ({
        tag: el.tagName,
        type: el.type,
        placeholder: el.placeholder,
        class: el.className,
        id: el.id,
        text: el.innerText?.trim(),
        visible: window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden'
      }))
    };
  });
  console.log('\nMODAL DOM INSPECTION:');
  console.log(JSON.stringify(modalInfo, null, 2));

  errs = flushErrors();
  errs.filter(e => e.type === 'error' || e.type === 'pageerror').forEach(e =>
    console.log(`  [${e.type.toUpperCase()}] ${e.text}`)
  );

  // ─── STEP 3: Login ──────────────────────────────────────────────────────────
  console.log('\n==============================');
  console.log('STEP 3: Login');
  console.log('==============================');

  // Find visible email input specifically
  const emailInputHandle = await page.evaluate(() => {
    const inputs = document.querySelectorAll('input[type="email"], input[name="email"], input[placeholder*="email" i]');
    return Array.from(inputs).map(el => {
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return {
        id: el.id,
        class: el.className,
        type: el.type,
        placeholder: el.placeholder,
        display: style.display,
        visibility: style.visibility,
        opacity: style.opacity,
        width: rect.width,
        height: rect.height,
        top: rect.top,
        left: rect.left,
      };
    });
  });
  console.log('ALL EMAIL INPUTS (visibility info):');
  console.log(JSON.stringify(emailInputHandle, null, 2));

  // Try to fill the VISIBLE email input
  const visibleEmailInput = await page.locator('input[type="email"]:visible, input[placeholder*="email" i]:visible').first();
  const emailCount = await visibleEmailInput.count();
  console.log(`Visible email inputs count: ${emailCount}`);

  if (emailCount > 0) {
    await visibleEmailInput.fill('prabhat@lnsbotz.ai');
    console.log('Filled email: prabhat@lnsbotz.ai');
  } else {
    console.log('WARNING: No visible email input found, trying force fill...');
    try {
      await page.locator('input[type="email"]').first().fill('prabhat@lnsbotz.ai', { force: true });
      console.log('Force-filled email');
    } catch(e) {
      console.log('FAILED to fill email:', e.message);
    }
  }

  const visiblePasswordInput = await page.locator('input[type="password"]:visible').first();
  const pwCount = await visiblePasswordInput.count();
  console.log(`Visible password inputs count: ${pwCount}`);

  if (pwCount > 0) {
    await visiblePasswordInput.fill(process.env.LNS_TEST_PASSWORD);
    console.log('Filled password');
  } else {
    try {
      await page.locator('input[type="password"]').first().fill(process.env.LNS_TEST_PASSWORD, { force: true });
      console.log('Force-filled password');
    } catch(e) {
      console.log('FAILED to fill password:', e.message);
    }
  }

  await shot(page, '03a_login_filled');

  // Clear network log before click
  Object.keys(networkRequests).forEach(k => delete networkRequests[k]);

  // Click Sign In
  const signInSelectors = [
    'button:has-text("Sign In"):visible',
    'button:has-text("Log In"):visible',
    'button:has-text("Login"):visible',
    'button[type="submit"]:visible',
    '.modal button[type="submit"]',
    '.modal button:has-text("Sign")',
  ];

  let clicked = false;
  for (const sel of signInSelectors) {
    try {
      const btn = page.locator(sel).first();
      const cnt = await btn.count();
      if (cnt > 0) {
        const btnText = await btn.textContent();
        console.log(`Clicking button: "${btnText?.trim()}" (selector: ${sel})`);
        await btn.click();
        clicked = true;
        break;
      }
    } catch(e) { /* continue */ }
  }

  if (!clicked) {
    console.log('FAILED to find Sign In button - dumping all buttons:');
    const allBtns = await page.evaluate(() =>
      Array.from(document.querySelectorAll('button')).map(b => ({
        text: b.innerText?.trim(),
        type: b.type,
        class: b.className,
        visible: window.getComputedStyle(b).display !== 'none'
      }))
    );
    console.log(JSON.stringify(allBtns, null, 2));
  }

  await sleep(4000);
  await shot(page, '03b_after_signin');

  console.log(`URL after sign in: ${page.url()}`);

  // Capture error messages
  const loginErrors = await page.evaluate(() => {
    const errorEls = document.querySelectorAll('[class*="error" i], [class*="alert" i], [role="alert"], .text-red-500, .text-red-600, [class*="danger"], [class*="invalid"]');
    return Array.from(errorEls).map(el => el.innerText?.trim()).filter(t => t);
  });
  if (loginErrors.length) {
    console.log('\nERROR MESSAGES on page:', loginErrors);
  }

  // Network requests
  console.log('\nNETWORK REQUESTS during login:');
  Object.values(networkRequests).forEach(r => {
    console.log(`  [${r.method}] ${r.url}`);
    console.log(`  STATUS: ${r.status}`);
    if (r.body) console.log(`  BODY: ${r.body.substring(0, 800)}`);
    console.log('  ---');
  });

  errs = flushErrors();
  console.log(`\nCONSOLE after login (${errs.length} total):`);
  errs.filter(e => e.type !== 'log').forEach(e =>
    console.log(`  [${e.type.toUpperCase()}] ${e.text}`)
  );

  // ─── STEP 4: Nav check ──────────────────────────────────────────────────────
  console.log('\n==============================');
  console.log('STEP 4: Nav after login');
  console.log('==============================');
  await sleep(2000);
  await shot(page, '04_nav_after_login');

  const navContent = await page.evaluate(() => {
    const nav = document.querySelector('nav, header, [class*="navbar" i], [class*="topbar" i]');
    return nav ? { class: nav.className, text: nav.innerText?.trim().substring(0, 400) } : { error: 'NO NAV FOUND' };
  });
  console.log('NAV:', JSON.stringify(navContent));

  const loggedInCheck = await page.evaluate(() => {
    const body = document.body.innerText;
    return {
      hasLogout: body.includes('Logout') || body.includes('Sign Out') || body.includes('Log Out'),
      hasDashboard: body.includes('Dashboard') || body.includes('dashboard'),
      hasUserName: body.includes('prabhat') || body.includes('Prabhat'),
      bodyPreview: body.substring(0, 500)
    };
  });
  console.log('LOGGED IN CHECK:', JSON.stringify(loggedInCheck, null, 2));

  // ─── STEP 5: Scroll down ─────────────────────────────────────────────────────
  console.log('\n==============================');
  console.log('STEP 5: Scroll down');
  console.log('==============================');
  await page.evaluate(() => window.scrollTo(0, 400));
  await sleep(1000);
  await shot(page, '05_scrolled');
  await page.evaluate(() => window.scrollTo(0, 900));
  await sleep(1000);
  await shot(page, '05b_scrolled_more');

  const pageStructure = await page.evaluate(() => {
    const sections = document.querySelectorAll('section, [class*="section" i], [class*="dashboard" i], [class*="products" i], [class*="grid" i]');
    return Array.from(sections).slice(0, 8).map(el => ({
      tag: el.tagName,
      id: el.id,
      class: el.className.substring(0,80),
      textPreview: el.innerText?.trim().substring(0, 100)
    }));
  });
  console.log('PAGE SECTIONS:');
  console.log(JSON.stringify(pageStructure, null, 2));

  errs = flushErrors();
  errs.filter(e => e.type === 'error' || e.type === 'pageerror').forEach(e =>
    console.log(`  [${e.type.toUpperCase()}] ${e.text}`)
  );

  // ─── STEP 6: Click Legal Notice ──────────────────────────────────────────
  console.log('\n==============================');
  console.log('STEP 6: Click Legal Notice card');
  console.log('==============================');
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(500);

  const legalEl = await page.locator('text=Legal Notice').first();
  const legalCount = await legalEl.count();
  if (legalCount > 0) {
    await legalEl.click();
    await sleep(2500);
    await shot(page, '06_after_legal_click');
    console.log(`URL after Legal Notice click: ${page.url()}`);

    const panelInfo = await page.evaluate(() => {
      const all = document.querySelectorAll('[class*="panel" i], [class*="drawer" i], [class*="product-detail" i], [class*="modal" i], [role="dialog"]');
      return Array.from(all).filter(el => {
        const s = window.getComputedStyle(el);
        return s.display !== 'none' && s.visibility !== 'hidden' && el.getBoundingClientRect().width > 0;
      }).map(el => ({
        class: el.className.substring(0,100),
        text: el.innerText?.trim().substring(0, 200)
      }));
    });
    console.log('PANEL/MODAL elements:', JSON.stringify(panelInfo, null, 2));

    // Check if page changed
    const pageText = await page.evaluate(() => document.body.innerText.substring(0, 600));
    console.log('PAGE TEXT after click:', pageText);
  } else {
    console.log('Legal Notice element NOT FOUND');
    const allText = await page.evaluate(() => {
      const cards = document.querySelectorAll('[class*="card" i], [class*="product" i], li, [class*="item" i]');
      return Array.from(cards).slice(0, 15).map(el => el.innerText?.trim().substring(0, 60)).filter(t => t);
    });
    console.log('All card texts:', allText);
  }

  errs = flushErrors();
  errs.filter(e => e.type === 'error' || e.type === 'pageerror').forEach(e =>
    console.log(`  [${e.type.toUpperCase()}] ${e.text}`)
  );

  // ─── STEP 7: Type and run ─────────────────────────────────────────────────
  console.log('\n==============================');
  console.log('STEP 7: Type in textarea and Run');
  console.log('==============================');

  const textareaHandle = await page.$('textarea:visible, [contenteditable="true"]:visible');
  if (textareaHandle) {
    console.log('Found textarea');
    await textareaHandle.fill('You owe Rs 50000. Pay in 15 days or face court action.');
    await sleep(500);
    await shot(page, '07a_textarea_filled');

    Object.keys(networkRequests).forEach(k => delete networkRequests[k]);

    const runBtn = await page.locator('button:has-text("Run"):visible, button:has-text("Generate"):visible, button:has-text("Submit"):visible, button[type="submit"]:visible').first();
    const runCount = await runBtn.count();
    if (runCount > 0) {
      const btnTxt = await runBtn.textContent();
      console.log(`Clicking run button: "${btnTxt?.trim()}"`);
      await runBtn.click();
      await sleep(6000);
      await shot(page, '07b_after_run');

      const resultText = await page.evaluate(() => {
        const result = document.querySelector('[class*="result" i], [class*="output" i], [class*="response" i], [class*="generated" i], [class*="answer" i]');
        return result ? result.innerText?.trim().substring(0, 500) : null;
      });
      console.log('RESULT CONTENT:', resultText || 'No result element found');

      const pageTextAfterRun = await page.evaluate(() => document.body.innerText.substring(0, 800));
      console.log('PAGE TEXT after run:', pageTextAfterRun);

    } else {
      console.log('No Run button found');
      const allBtns2 = await page.$$eval('button:visible', els => els.map(b => b.innerText?.trim()));
      console.log('Visible buttons:', allBtns2);
    }
  } else {
    console.log('No visible textarea found');
    const inputInfo = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('textarea, input[type="text"]')).map(el => {
        const s = window.getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { tag: el.tagName, class: el.className.substring(0,60), display: s.display, visibility: s.visibility, width: r.width, height: r.height };
      });
    });
    console.log('All textareas/inputs:', JSON.stringify(inputInfo, null, 2));
    await shot(page, '07_no_textarea');
  }

  console.log('\nNETWORK REQUESTS during Run:');
  Object.values(networkRequests).forEach(r => {
    console.log(`  [${r.method}] ${r.url}`);
    console.log(`  STATUS: ${r.status}`);
    if (r.body) console.log(`  BODY: ${r.body.substring(0, 1500)}`);
    console.log('  ---');
  });

  errs = flushErrors();
  console.log(`\nCONSOLE after Run (${errs.length} total):`);
  errs.filter(e => e.type !== 'log').forEach(e =>
    console.log(`  [${e.type.toUpperCase()}] ${e.text}`)
  );

  // ─── STEP 10: Continue with Google ────────────────────────────────────────
  console.log('\n==============================');
  console.log('STEP 10: Continue with Google');
  console.log('==============================');

  // Go back to get modal
  await page.goto('https://lnsbotz.latenightstack.com', { waitUntil: 'networkidle', timeout: 20000 });
  await sleep(1500);

  const getStartedBtn2 = await page.locator('a:has-text("Get Started"), button:has-text("Get Started")').first();
  if (await getStartedBtn2.count() > 0) {
    await getStartedBtn2.click();
    await sleep(1500);
    console.log('Clicked Get Started to open modal');
  }

  await shot(page, '10a_modal_for_google');

  // Find Google button
  const googleBtnLocator = page.locator('button:has-text("Google"), a:has-text("Google"), [class*="google" i]').first();
  const googleCount = await googleBtnLocator.count();
  if (googleCount > 0) {
    const googleBtnText = await googleBtnLocator.textContent();
    console.log(`Found Google button: "${googleBtnText?.trim()}"`);

    Object.keys(networkRequests).forEach(k => delete networkRequests[k]);
    const [popup] = await Promise.all([
      context.waitForEvent('page', { timeout: 5000 }).catch(() => null),
      googleBtnLocator.click()
    ]);

    await sleep(3000);
    await shot(page, '10b_after_google_click');

    if (popup) {
      console.log(`Google popup opened: ${popup.url()}`);
      await popup.screenshot({ path: path.join(SCREENSHOTS_DIR, '10c_google_popup.png') });
      console.log('[SCREENSHOT] 10c_google_popup.png');
    } else {
      console.log('No popup opened');
      console.log(`Current URL: ${page.url()}`);
    }

    console.log('\nNETWORK after Google click:');
    Object.values(networkRequests).forEach(r => {
      console.log(`  [${r.method}] ${r.url} -> ${r.status}`);
    });
  } else {
    console.log('Google button NOT FOUND - checking modal content:');
    const modalText = await page.evaluate(() => {
      const modal = document.querySelector('.modal, [role="dialog"]');
      return modal ? modal.innerText?.trim() : 'NO MODAL';
    });
    console.log('MODAL TEXT:', modalText);
    await shot(page, '10_no_google_btn');
  }

  errs = flushErrors();
  errs.filter(e => e.type === 'error' || e.type === 'pageerror').forEach(e =>
    console.log(`  [${e.type.toUpperCase()}] ${e.text}`)
  );

  // ─── SUMMARY ─────────────────────────────────────────────────────────────
  console.log('\n==============================');
  console.log('ALL NETWORK REQUESTS CAPTURED');
  console.log('==============================');
  allNetworkRequests.forEach(r => {
    console.log(`[${r.method}] ${r.url} -> ${r.status} @ ${r.time}`);
  });

  await browser.close();
  console.log('\nDONE. Screenshots saved to:', SCREENSHOTS_DIR);
})();
