if (!process.env.LNS_TEST_PASSWORD) { console.error('Set LNS_TEST_PASSWORD before running this script.'); process.exit(1); }
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const SCREENSHOT_DIR = '/Users/xxvirusxx/PY/Bots/lns_screenshots';
if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true });
  const consoleErrors = [];
  const networkErrors = [];
  let authToken = null;

  // ─────────────────────────────────────────────────────────────────────────
  // ISSUE 1: UI BREAKS AFTER LOGIN
  // ─────────────────────────────────────────────────────────────────────────
  console.log('\n========== ISSUE 1: UI AFTER LOGIN ==========');

  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  const page = await ctx.newPage();

  // Capture all console messages
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    if (type === 'error' || type === 'warning') {
      consoleErrors.push(`[${type.toUpperCase()}] ${text}`);
    }
    console.log(`  CONSOLE [${type}]: ${text}`);
  });

  // Capture network failures
  page.on('requestfailed', req => {
    networkErrors.push(`FAILED: ${req.method()} ${req.url()} — ${req.failure().errorText}`);
    console.log(`  NET FAIL: ${req.method()} ${req.url()} — ${req.failure().errorText}`);
  });

  // Also intercept XHR/fetch responses to log API calls
  page.on('response', async resp => {
    const url = resp.url();
    const status = resp.status();
    if (url.includes('/api/') || url.includes('lnsbotz')) {
      console.log(`  RESPONSE: ${resp.request().method()} ${url} → ${status}`);
    }
  });

  // Step 1: Navigate to home
  console.log('\n[STEP 1] Navigating to homepage...');
  await page.goto('https://lnsbotz.latenightstack.com', { waitUntil: 'networkidle', timeout: 30000 });
  await page.screenshot({ path: `${SCREENSHOT_DIR}/debug_01_homepage.png`, fullPage: false });
  console.log('  Screenshot: debug_01_homepage.png');

  // Step 2: Click Get Started
  console.log('\n[STEP 2] Clicking Get Started...');
  try {
    const btn = page.locator('text=Get Started').first();
    await btn.waitFor({ timeout: 10000 });
    await btn.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/debug_02_modal_open.png`, fullPage: false });
    console.log('  Screenshot: debug_02_modal_open.png');
  } catch (e) {
    console.log(`  ERROR: ${e.message}`);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/debug_02_fail.png`, fullPage: true });
  }

  // Step 3: Switch to Login tab
  console.log('\n[STEP 3] Switching to Login tab...');
  try {
    // Look for Sign In / Login tab
    const loginTab = page.locator('text=Sign In, text=Login, [role="tab"]:has-text("Sign In"), [role="tab"]:has-text("Login")').first();
    await loginTab.waitFor({ timeout: 8000 });
    await loginTab.click();
    await page.waitForTimeout(500);
    console.log('  Clicked login tab');
  } catch (e) {
    console.log(`  Login tab not found or already on it: ${e.message}`);
  }

  // Step 4: Fill login form
  console.log('\n[STEP 4] Filling login form...');
  try {
    const emailField = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i], input[placeholder*="Email"]').first();
    await emailField.waitFor({ timeout: 8000 });
    await emailField.fill('prabhat@lnsbotz.ai');

    const pwField = page.locator('input[type="password"]').first();
    await pwField.fill(process.env.LNS_TEST_PASSWORD);

    await page.screenshot({ path: `${SCREENSHOT_DIR}/debug_03_login_filled.png`, fullPage: false });
    console.log('  Filled email + password. Screenshot: debug_03_login_filled.png');
  } catch (e) {
    console.log(`  ERROR filling form: ${e.message}`);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/debug_03_fail.png`, fullPage: true });
  }

  // Step 5: Submit login and capture what happens
  console.log('\n[STEP 5] Submitting login...');
  let loginResponseBody = null;
  try {
    // Intercept the login API response to grab the token
    const loginResponsePromise = page.waitForResponse(
      resp => (resp.url().includes('/login') || resp.url().includes('/auth') || resp.url().includes('/token') || resp.url().includes('/signin')) && resp.request().method() === 'POST',
      { timeout: 15000 }
    ).catch(() => null);

    // Click the submit button
    const submitBtn = page.locator('button[type="submit"], button:has-text("Sign In"), button:has-text("Login"), button:has-text("Log In")').first();
    await submitBtn.waitFor({ timeout: 8000 });
    await submitBtn.click();
    console.log('  Clicked submit');

    // Wait for navigation or network idle
    await Promise.race([
      page.waitForNavigation({ timeout: 10000 }).catch(() => {}),
      page.waitForTimeout(5000),
    ]);

    const loginResp = await loginResponsePromise;
    if (loginResp) {
      const status = loginResp.status();
      console.log(`  Login API response: ${status} from ${loginResp.url()}`);
      try {
        loginResponseBody = await loginResp.json();
        console.log(`  Login response body: ${JSON.stringify(loginResponseBody)}`);
        // Extract token
        authToken = loginResponseBody?.access_token || loginResponseBody?.token || loginResponseBody?.data?.token || loginResponseBody?.data?.access_token;
        if (authToken) {
          console.log(`  Token captured: ${authToken.substring(0, 40)}...`);
        }
      } catch (e2) {
        const text = await loginResp.text().catch(() => '');
        console.log(`  Login response text: ${text.substring(0, 500)}`);
      }
    } else {
      console.log('  No login API response intercepted');
    }

    // Wait a bit more for page to settle
    await page.waitForTimeout(3000);

    const currentUrl = page.url();
    console.log(`  Current URL after login: ${currentUrl}`);

    // Take screenshot immediately after login
    await page.screenshot({ path: `${SCREENSHOT_DIR}/debug_04_after_login.png`, fullPage: false });
    await page.screenshot({ path: `${SCREENSHOT_DIR}/debug_04_after_login_full.png`, fullPage: true });
    console.log('  Screenshot: debug_04_after_login.png (viewport) + debug_04_after_login_full.png (full page)');

  } catch (e) {
    console.log(`  ERROR during login: ${e.message}`);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/debug_05_login_fail.png`, fullPage: true });
  }

  // Step 6: Inspect layout issues
  console.log('\n[STEP 6] Inspecting layout issues...');
  try {
    const layoutInfo = await page.evaluate(() => {
      const results = {};

      // Check body
      const body = document.body;
      const bodyStyle = window.getComputedStyle(body);
      results.body = {
        overflow: bodyStyle.overflow,
        overflowX: bodyStyle.overflowX,
        overflowY: bodyStyle.overflowY,
        height: body.scrollHeight,
        width: body.scrollWidth,
      };

      // Check for nav/header
      const nav = document.querySelector('nav, header, [class*="nav"], [class*="header"]');
      if (nav) {
        const navStyle = window.getComputedStyle(nav);
        results.nav = {
          tag: nav.tagName,
          classes: nav.className,
          position: navStyle.position,
          zIndex: navStyle.zIndex,
          top: navStyle.top,
          height: nav.offsetHeight,
          visible: nav.offsetHeight > 0,
        };
      }

      // Check for hero section
      const hero = document.querySelector('[class*="hero"], [class*="Hero"], section:first-of-type, .hero');
      if (hero) {
        const heroStyle = window.getComputedStyle(hero);
        results.hero = {
          classes: hero.className,
          position: heroStyle.position,
          zIndex: heroStyle.zIndex,
          marginTop: heroStyle.marginTop,
          paddingTop: heroStyle.paddingTop,
          height: hero.offsetHeight,
          top: hero.getBoundingClientRect().top,
        };
      }

      // Check for dashboard/main content
      const main = document.querySelector('main, [class*="dashboard"], [class*="Dashboard"], [id*="dashboard"]');
      if (main) {
        const mainStyle = window.getComputedStyle(main);
        results.main = {
          tag: main.tagName,
          classes: main.className,
          position: mainStyle.position,
          zIndex: mainStyle.zIndex,
          marginTop: mainStyle.marginTop,
          paddingTop: mainStyle.paddingTop,
          height: main.offsetHeight,
          top: main.getBoundingClientRect().top,
        };
      }

      // Check for any modals still open
      const modals = document.querySelectorAll('[class*="modal"], [class*="Modal"], [role="dialog"]');
      results.openModals = Array.from(modals).filter(m => {
        const s = window.getComputedStyle(m);
        return s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity) > 0;
      }).map(m => ({ classes: m.className, zIndex: window.getComputedStyle(m).zIndex }));

      // Check for overlapping elements at top of page
      const topElements = [];
      for (let x = 100; x <= 1100; x += 200) {
        const el = document.elementFromPoint(x, 100);
        if (el) topElements.push({ x, tag: el.tagName, classes: el.className.toString().substring(0, 80) });
      }
      results.topElements = topElements;

      // DOM visible text at top level
      results.pageTitle = document.title;
      results.h1s = Array.from(document.querySelectorAll('h1')).map(h => h.textContent.trim()).slice(0, 5);
      results.visibleText = document.body.innerText.substring(0, 500);

      // Check localStorage/sessionStorage for token
      const lsKeys = Object.keys(localStorage);
      const ssKeys = Object.keys(sessionStorage);
      results.storageKeys = { localStorage: lsKeys, sessionStorage: ssKeys };

      // Look for token in storage
      for (const k of lsKeys) {
        const v = localStorage.getItem(k);
        if (v && (v.includes('eyJ') || k.toLowerCase().includes('token') || k.toLowerCase().includes('auth'))) {
          results.tokenInStorage = `localStorage[${k}] = ${v.substring(0, 100)}`;
          break;
        }
      }
      for (const k of ssKeys) {
        const v = sessionStorage.getItem(k);
        if (v && (v.includes('eyJ') || k.toLowerCase().includes('token') || k.toLowerCase().includes('auth'))) {
          results.tokenInStorage = results.tokenInStorage || `sessionStorage[${k}] = ${v.substring(0, 100)}`;
          break;
        }
      }

      // Check cookies
      results.cookies = document.cookie.substring(0, 300);

      return results;
    });

    console.log('\n  LAYOUT INSPECTION RESULT:');
    console.log(JSON.stringify(layoutInfo, null, 2));

    // Also try to extract token from storage if we didn't get it from network
    if (!authToken && layoutInfo.tokenInStorage) {
      const tokenMatch = layoutInfo.tokenInStorage.match(/eyJ[\w.-]+/);
      if (tokenMatch) {
        authToken = tokenMatch[0];
        console.log(`\n  Token from storage: ${authToken.substring(0, 40)}...`);
      }
    }

  } catch (e) {
    console.log(`  ERROR in layout inspection: ${e.message}`);
  }

  // Step 7: Check all CSS z-index and overflow issues
  console.log('\n[STEP 7] Checking z-index and overflow issues...');
  try {
    const cssIssues = await page.evaluate(() => {
      const issues = [];
      const allElements = document.querySelectorAll('*');
      const highZIndex = [];
      const overflowHidden = [];

      for (const el of allElements) {
        const style = window.getComputedStyle(el);
        const zIndex = parseInt(style.zIndex);
        if (!isNaN(zIndex) && zIndex > 10) {
          highZIndex.push({
            tag: el.tagName,
            id: el.id,
            classes: el.className.toString().substring(0, 60),
            zIndex,
            position: style.position,
            display: style.display,
          });
        }
        if ((style.overflow === 'hidden' || style.overflowX === 'hidden') && el.scrollWidth > el.clientWidth) {
          overflowHidden.push({
            tag: el.tagName,
            classes: el.className.toString().substring(0, 60),
            scrollWidth: el.scrollWidth,
            clientWidth: el.clientWidth,
          });
        }
      }

      return {
        highZIndex: highZIndex.sort((a, b) => b.zIndex - a.zIndex).slice(0, 20),
        overflowCulprits: overflowHidden.slice(0, 10),
      };
    });

    console.log('\n  Z-INDEX ELEMENTS (top 20):');
    console.log(JSON.stringify(cssIssues.highZIndex, null, 2));
    console.log('\n  OVERFLOW HIDDEN CULPRITS:');
    console.log(JSON.stringify(cssIssues.overflowCulprits, null, 2));
  } catch (e) {
    console.log(`  ERROR: ${e.message}`);
  }

  await ctx.close();

  // ─────────────────────────────────────────────────────────────────────────
  // ISSUE 2: PRODUCTS API
  // ─────────────────────────────────────────────────────────────────────────
  console.log('\n\n========== ISSUE 2: PRODUCTS API ==========');

  // If we don't have a token from Step 5, try to get one via direct API call
  if (!authToken) {
    console.log('\n[API] Getting token via direct login API call...');
    try {
      // Try common login endpoints
      const loginEndpoints = [
        'https://lnsbotz.latenightstack.com/api/v1/auth/login',
        'https://lnsbotz.latenightstack.com/api/v1/users/login',
        'https://lnsbotz.latenightstack.com/api/auth/login',
        'https://lnsbotz.latenightstack.com/api/login',
        'https://lnsbotz.latenightstack.com/auth/login',
      ];

      for (const endpoint of loginEndpoints) {
        const resp = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: 'prabhat@lnsbotz.ai', password: process.env.LNS_TEST_PASSWORD }),
        }).catch(() => null);

        if (resp && resp.ok) {
          const data = await resp.json().catch(() => null);
          console.log(`  Login endpoint ${endpoint} → ${resp.status}`);
          console.log(`  Response: ${JSON.stringify(data)}`);
          authToken = data?.access_token || data?.token || data?.data?.token;
          if (authToken) break;
        } else if (resp) {
          console.log(`  Login endpoint ${endpoint} → ${resp.status}`);
          const text = await resp.text().catch(() => '');
          console.log(`  Response: ${text.substring(0, 200)}`);
        }
      }
    } catch (e) {
      console.log(`  ERROR: ${e.message}`);
    }
  }

  // Now run all API checks in a headless browser context for accurate CORS/cookie behavior
  const ctx2 = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page2 = await ctx2.newPage();

  page2.on('console', msg => {
    console.log(`  PAGE2 CONSOLE [${msg.type()}]: ${msg.text()}`);
  });

  // Step A: Get auth token via the site's login (browser context to handle cookies/CSRF)
  console.log('\n[STEP A] Logging in to get auth token...');
  try {
    await page2.goto('https://lnsbotz.latenightstack.com', { waitUntil: 'networkidle', timeout: 30000 });

    // Intercept login response
    const tokenPromise = new Promise((resolve) => {
      page2.on('response', async resp => {
        const url = resp.url();
        if ((url.includes('/login') || url.includes('/auth') || url.includes('/token') || url.includes('/signin')) && resp.request().method() === 'POST') {
          try {
            const body = await resp.json();
            const token = body?.access_token || body?.token || body?.data?.token || body?.data?.access_token;
            if (token) resolve(token);
          } catch (e) {}
        }
      });
      setTimeout(() => resolve(null), 20000);
    });

    // Try to login
    const getStartedBtn = page2.locator('text=Get Started').first();
    await getStartedBtn.click().catch(() => {});
    await page2.waitForTimeout(1500);

    // Click login/sign in tab
    await page2.locator('text=Sign In').first().click().catch(() => {});
    await page2.locator('text=Login').first().click().catch(() => {});
    await page2.waitForTimeout(500);

    // Fill
    await page2.locator('input[type="email"]').first().fill('prabhat@lnsbotz.ai').catch(() => {});
    await page2.locator('input[type="password"]').first().fill(process.env.LNS_TEST_PASSWORD).catch(() => {});
    await page2.locator('button[type="submit"]').first().click().catch(() => {});

    await page2.waitForTimeout(5000);

    const resolvedToken = await tokenPromise;
    if (resolvedToken && !authToken) {
      authToken = resolvedToken;
      console.log(`  Token from browser login: ${authToken.substring(0, 40)}...`);
    }

    // Also check storage
    if (!authToken) {
      const stored = await page2.evaluate(() => {
        for (const k of Object.keys(localStorage)) {
          const v = localStorage.getItem(k);
          if (v && v.includes('eyJ')) return v;
        }
        for (const k of Object.keys(sessionStorage)) {
          const v = sessionStorage.getItem(k);
          if (v && v.includes('eyJ')) return v;
        }
        // Check for token nested in JSON
        for (const k of Object.keys(localStorage)) {
          try {
            const v = JSON.parse(localStorage.getItem(k));
            const t = v?.access_token || v?.token || v?.data?.token;
            if (t) return t;
          } catch (e) {}
        }
        return null;
      });
      if (stored && !authToken) {
        authToken = stored.match(/eyJ[\w.-]+/)?.[0] || stored;
        console.log(`  Token from storage: ${authToken.substring(0, 40)}...`);
      }
    }

  } catch (e) {
    console.log(`  ERROR: ${e.message}`);
  }

  console.log(`\n  Auth token available: ${authToken ? 'YES (' + authToken.substring(0, 30) + '...)' : 'NO'}`);

  // Step B: Hit /api/v1/products/catalog
  console.log('\n[STEP B] GET /api/v1/products/catalog...');
  try {
    const result = await page2.evaluate(async (token) => {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const resp = await fetch('https://lnsbotz.latenightstack.com/api/v1/products/catalog', { headers });
      const body = await resp.text();
      return { status: resp.status, headers: Object.fromEntries(resp.headers.entries()), body };
    }, authToken);
    console.log(`  Status: ${result.status}`);
    console.log(`  Response Headers: ${JSON.stringify(result.headers)}`);
    console.log(`  Body: ${result.body.substring(0, 1000)}`);
  } catch (e) {
    console.log(`  ERROR: ${e.message}`);
  }

  // Step C: POST /api/v1/products/document/analyze
  console.log('\n[STEP C] POST /api/v1/products/document/analyze...');
  try {
    const result = await page2.evaluate(async (token) => {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const payload = {
        product: 'legal_notice',
        text: 'You owe Rs 50000. Pay in 15 days or face court action under Section 138.',
        output_language: 'en',
      };
      const resp = await fetch('https://lnsbotz.latenightstack.com/api/v1/products/document/analyze', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });
      const body = await resp.text();
      return { status: resp.status, headers: Object.fromEntries(resp.headers.entries()), body };
    }, authToken);
    console.log(`  Status: ${result.status}`);
    console.log(`  Response Headers: ${JSON.stringify(result.headers)}`);
    console.log(`  Body: ${result.body.substring(0, 2000)}`);
  } catch (e) {
    console.log(`  ERROR: ${e.message}`);
  }

  // Step D: Check /docs
  console.log('\n[STEP D] Checking /docs...');
  try {
    await page2.goto('https://lnsbotz.latenightstack.com/docs', { waitUntil: 'networkidle', timeout: 20000 });
    await page2.waitForTimeout(3000);
    await page2.screenshot({ path: `${SCREENSHOT_DIR}/debug_05_docs.png`, fullPage: true });
    console.log('  Screenshot: debug_05_docs.png');

    const docsContent = await page2.evaluate(() => {
      // Extract all route paths visible in FastAPI docs
      const operationIds = document.querySelectorAll('.opblock-summary-path, .opblock .opblock-summary-path span, [data-path]');
      const paths = Array.from(operationIds).map(el => el.textContent.trim()).filter(t => t);

      // Also check for section titles / tags
      const tags = Array.from(document.querySelectorAll('.opblock-tag, h2, h3')).map(el => el.textContent.trim()).filter(t => t);

      return {
        title: document.title,
        paths: [...new Set(paths)].slice(0, 50),
        tags: [...new Set(tags)].slice(0, 30),
        pageText: document.body.innerText.substring(0, 3000),
      };
    });

    console.log(`  Page title: ${docsContent.title}`);
    console.log(`  API Paths found: ${JSON.stringify(docsContent.paths)}`);
    console.log(`  Tags/Sections: ${JSON.stringify(docsContent.tags)}`);
    console.log(`  Page text (first 2000 chars):\n${docsContent.pageText.substring(0, 2000)}`);
  } catch (e) {
    console.log(`  ERROR: ${e.message}`);
  }

  // Step E: Try alternate product endpoints
  console.log('\n[STEP E] Trying alternate product endpoints...');
  const endpoints = [
    ['GET', 'https://lnsbotz.latenightstack.com/api/v1/products'],
    ['GET', 'https://lnsbotz.latenightstack.com/api/v1/products/list'],
    ['GET', 'https://lnsbotz.latenightstack.com/api/v1/products/catalog'],
    ['GET', 'https://lnsbotz.latenightstack.com/api/v1/'],
    ['GET', 'https://lnsbotz.latenightstack.com/api/'],
  ];

  for (const [method, url] of endpoints) {
    try {
      const result = await page2.evaluate(async ({ method, url, token }) => {
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const resp = await fetch(url, { method, headers });
        const body = await resp.text();
        return { status: resp.status, body: body.substring(0, 300) };
      }, { method, url, token: authToken });
      console.log(`  ${method} ${url} → ${result.status}: ${result.body.substring(0, 150)}`);
    } catch (e) {
      console.log(`  ERROR ${method} ${url}: ${e.message}`);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SUMMARY
  // ─────────────────────────────────────────────────────────────────────────
  console.log('\n\n========== SUMMARY ==========');
  console.log('\nConsole Errors collected:');
  if (consoleErrors.length === 0) {
    console.log('  (none)');
  } else {
    consoleErrors.forEach(e => console.log(`  ${e}`));
  }
  console.log('\nNetwork Failures collected:');
  if (networkErrors.length === 0) {
    console.log('  (none)');
  } else {
    networkErrors.forEach(e => console.log(`  ${e}`));
  }

  await ctx2.close();
  await browser.close();
  console.log('\nDone. Screenshots saved to:', SCREENSHOT_DIR);
})();
