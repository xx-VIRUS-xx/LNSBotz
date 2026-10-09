if (!process.env.LNS_TEST_PASSWORD) { console.error('Set LNS_TEST_PASSWORD before running this script.'); process.exit(1); }
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOTS_DIR = '/Users/xxvirusxx/PY/Bots/lns_screenshots';
if (!fs.existsSync(SCREENSHOTS_DIR)) fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

const consoleLog = [];
const networkLog = [];

async function shot(page, name) {
  const p = path.join(SCREENSHOTS_DIR, `${name}.png`);
  await page.screenshot({ path: p, fullPage: false });
  console.log(`[SCREENSHOT] ${p}`);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Log ALL console
  page.on('console', msg => {
    consoleLog.push({ type: msg.type(), text: msg.text() });
    if (msg.type() === 'error' || msg.type() === 'warn') {
      console.log(`[BROWSER ${msg.type().toUpperCase()}] ${msg.text()}`);
    }
  });
  page.on('pageerror', err => {
    consoleLog.push({ type: 'pageerror', text: err.message });
    console.log(`[PAGE ERROR] ${err.message}`);
    console.log(`[STACK] ${err.stack}`);
  });

  // Log ALL network
  page.on('request', req => {
    if (!req.url().startsWith('data:')) {
      networkLog.push({ dir: 'REQ', method: req.method(), url: req.url(), time: Date.now() });
    }
  });
  page.on('response', async res => {
    const url = res.url();
    if (url.startsWith('data:')) return;
    let body = '';
    try { body = await res.text(); if (body.length > 2000) body = body.substring(0,2000)+'[truncated]'; } catch(e) {}
    networkLog.push({ dir: 'RES', method: res.request().method(), url, status: res.status(), body, time: Date.now() });
    // Print anything API/auth related immediately
    if (url.includes('/api/') || url.includes('supabase') || url.includes('auth') || url.includes('.ai/') || url.includes('token') || url.includes('lnsbotz')) {
      console.log(`[NETWORK] ${res.request().method()} ${url} -> ${res.status()}`);
      if (body && body.trim()) console.log(`  BODY: ${body.substring(0, 500)}`);
    }
  });

  // ═══════════════════════════════════════════════════════════
  console.log('\n══════════════════════════════════════════════');
  console.log('STEP 1: Open homepage');
  console.log('══════════════════════════════════════════════');
  await page.goto('https://lnsbotz.latenightstack.com', { waitUntil: 'networkidle', timeout: 30000 });
  await sleep(2000);
  await shot(page, '01_homepage');
  console.log(`Title: ${await page.title()}`);
  console.log(`URL: ${page.url()}`);

  // ═══════════════════════════════════════════════════════════
  console.log('\n══════════════════════════════════════════════');
  console.log('STEP 2: Click "Get Started"');
  console.log('══════════════════════════════════════════════');
  await page.locator('text=Get Started').first().click();
  await sleep(2000);
  await shot(page, '02_modal_opened');

  // Inspect the modal carefully
  const modalState = await page.evaluate(() => {
    const overlay = document.getElementById('auth-overlay');
    const modal = document.querySelector('.modal');
    return {
      overlay: overlay ? {
        display: window.getComputedStyle(overlay).display,
        classes: overlay.className,
        innerHTML: overlay.innerHTML.substring(0, 3000)
      } : null,
      modal: modal ? {
        display: window.getComputedStyle(modal).display,
        classes: modal.className,
        innerHTML: modal.innerHTML.substring(0, 3000)
      } : null,
      allInputs: Array.from(document.querySelectorAll('input')).map(el => ({
        id: el.id,
        type: el.type,
        placeholder: el.placeholder,
        class: el.className,
        rect: el.getBoundingClientRect(),
        display: window.getComputedStyle(el).display,
        visibility: window.getComputedStyle(el).visibility
      }))
    };
  });
  console.log('OVERLAY state:', JSON.stringify(modalState.overlay?.classes));
  console.log('OVERLAY display:', modalState.overlay?.display);
  console.log('\nMODAL innerHTML (first 3000 chars):');
  console.log(modalState.modal?.innerHTML || 'NO MODAL');
  console.log('\nAll inputs on page:');
  console.log(JSON.stringify(modalState.allInputs, null, 2));

  // ═══════════════════════════════════════════════════════════
  console.log('\n══════════════════════════════════════════════');
  console.log('STEP 3: Attempt login - inspect what modal shows');
  console.log('══════════════════════════════════════════════');

  // The modal has tabs - check if we're on Login or Register tab
  const tabInfo = await page.evaluate(() => {
    const tabs = document.querySelectorAll('[class*="tab" i], [data-tab], [id*="tab" i]');
    return Array.from(tabs).map(el => ({
      id: el.id,
      class: el.className,
      text: el.innerText?.trim(),
      dataset: JSON.stringify(el.dataset),
      active: el.classList.contains('active') || el.getAttribute('aria-selected') === 'true'
    }));
  });
  console.log('TABS:', JSON.stringify(tabInfo, null, 2));

  // Check which form is currently shown
  const currentForm = await page.evaluate(() => {
    // Find all forms
    const forms = document.querySelectorAll('form, [id*="login" i], [id*="register" i], [id*="signup" i]');
    return Array.from(forms).map(el => ({
      id: el.id,
      class: el.className,
      display: window.getComputedStyle(el).display,
      innerHTML: el.innerHTML.substring(0, 1000)
    }));
  });
  console.log('\nFORMS:', JSON.stringify(currentForm, null, 2));

  // Check if there's a Login tab we need to click first
  const loginTab = await page.locator('[id*="login-tab" i], button:has-text("Login"), a:has-text("Login"), [class*="tab"]:has-text("Login")').first();
  const loginTabCount = await loginTab.count();
  if (loginTabCount > 0) {
    const tabText = await loginTab.textContent();
    console.log(`Clicking Login tab: "${tabText?.trim()}"`);
    await loginTab.click();
    await sleep(500);
  }

  // Now look for the login form specifically
  const loginFormCheck = await page.evaluate(() => {
    const lForm = document.getElementById('login-form') || document.querySelector('[id*="login-form"]') || document.querySelector('.login-form');
    const rForm = document.getElementById('register-form') || document.querySelector('[id*="register-form"]') || document.querySelector('.register-form');
    const lEmail = document.getElementById('l-email');
    const rEmail = document.getElementById('r-email');
    return {
      loginForm: lForm ? { display: window.getComputedStyle(lForm).display, id: lForm.id, class: lForm.className } : null,
      registerForm: rForm ? { display: window.getComputedStyle(rForm).display, id: rForm.id, class: rForm.className } : null,
      lEmailVisible: lEmail ? {
        display: window.getComputedStyle(lEmail).display,
        rect: lEmail.getBoundingClientRect(),
        parentDisplay: window.getComputedStyle(lEmail.parentElement).display,
        parent2Display: lEmail.parentElement ? window.getComputedStyle(lEmail.parentElement.parentElement).display : null,
        parentChain: (() => {
          let chain = [];
          let el = lEmail;
          for (let i = 0; i < 8; i++) {
            el = el.parentElement;
            if (!el) break;
            const s = window.getComputedStyle(el);
            chain.push({ tag: el.tagName, id: el.id, class: el.className.substring(0,40), display: s.display, visibility: s.visibility });
          }
          return chain;
        })()
      } : null,
      rEmailVisible: rEmail ? {
        display: window.getComputedStyle(rEmail).display,
        rect: rEmail.getBoundingClientRect()
      } : null
    };
  });
  console.log('\nFORM VISIBILITY CHECK:', JSON.stringify(loginFormCheck, null, 2));

  // Try clicking the LOGIN section specifically
  // First let's see what tabs/sections are in the modal
  const modalFullText = await page.evaluate(() => {
    const modal = document.querySelector('.modal');
    return modal ? modal.innerText?.trim() : 'NO MODAL';
  });
  console.log('\nMODAL TEXT:', modalFullText);

  // Try to click "Login" if there's a tab
  try {
    await page.locator('.modal >> text=Login').first().click({ timeout: 2000 });
    await sleep(500);
    console.log('Clicked Login tab in modal');
    await shot(page, '03_login_tab_clicked');
  } catch(e) {
    console.log('No Login tab to click or already on login:', e.message.substring(0, 100));
  }

  // Re-check visibility
  const lEmailInfo = await page.evaluate(() => {
    const el = document.getElementById('l-email');
    if (!el) return 'NOT FOUND';
    const rect = el.getBoundingClientRect();
    return {
      rect,
      display: window.getComputedStyle(el).display,
      visibility: window.getComputedStyle(el).visibility,
      offsetWidth: el.offsetWidth,
      offsetHeight: el.offsetHeight
    };
  });
  console.log('\nl-email input info:', JSON.stringify(lEmailInfo));

  // Use JavaScript to fill and submit login
  console.log('\nUsing JavaScript to fill login form...');
  const fillResult = await page.evaluate(async (creds) => {
    const emailEl = document.getElementById('l-email');
    const passEl = document.getElementById('l-password') || document.querySelector('input[type="password"]');

    if (!emailEl) return { error: 'No l-email element' };
    if (!passEl) return { error: 'No password element' };

    // Set values via native input value setter
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    nativeInputValueSetter.call(emailEl, creds.email);
    emailEl.dispatchEvent(new Event('input', { bubbles: true }));
    emailEl.dispatchEvent(new Event('change', { bubbles: true }));

    nativeInputValueSetter.call(passEl, creds.password);
    passEl.dispatchEvent(new Event('input', { bubbles: true }));
    passEl.dispatchEvent(new Event('change', { bubbles: true }));

    return { emailVal: emailEl.value, passVal: passEl.value ? '***filled***' : 'EMPTY', emailId: emailEl.id, passId: passEl.id };
  }, { email: 'prabhat@lnsbotz.ai', password: process.env.LNS_TEST_PASSWORD });

  console.log('Fill result:', JSON.stringify(fillResult));
  await shot(page, '03b_js_filled');

  // Find and click the login submit button
  const loginBtnInfo = await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    return Array.from(btns).map(b => ({
      id: b.id,
      class: b.className,
      text: b.innerText?.trim(),
      type: b.type,
      display: window.getComputedStyle(b).display,
      visibility: window.getComputedStyle(b).visibility,
      rect: b.getBoundingClientRect()
    }));
  });
  console.log('\nALL BUTTONS:', JSON.stringify(loginBtnInfo, null, 2));

  // Click the login submit via JS
  console.log('\nClicking login button via JS...');
  const clickResult = await page.evaluate(() => {
    // Find login button - try several selectors
    const loginBtn = document.getElementById('login-btn') ||
                     document.querySelector('button[onclick*="login"]') ||
                     document.querySelector('.modal button[type="submit"]') ||
                     document.querySelector('.login-form button') ||
                     Array.from(document.querySelectorAll('button')).find(b =>
                       b.innerText?.trim().toLowerCase() === 'login' &&
                       window.getComputedStyle(b).display !== 'none'
                     );
    if (!loginBtn) return { error: 'No login button found', allBtns: Array.from(document.querySelectorAll('button')).map(b => b.id + '/' + b.innerText?.trim().substring(0,20)) };
    loginBtn.click();
    return { clicked: loginBtn.id || loginBtn.className || loginBtn.innerText?.trim() };
  });
  console.log('Click result:', JSON.stringify(clickResult));

  await sleep(5000);
  await shot(page, '03c_after_login_attempt');
  console.log(`URL after login attempt: ${page.url()}`);

  // Check DOM after login attempt
  const postLoginDOM = await page.evaluate(() => {
    const overlay = document.getElementById('auth-overlay');
    const errorMsg = document.querySelector('[class*="error" i], [id*="error" i], [class*="alert" i], .text-red');
    return {
      overlayClass: overlay ? overlay.className : 'NOT FOUND',
      overlayDisplay: overlay ? window.getComputedStyle(overlay).display : 'N/A',
      errorMessage: errorMsg ? errorMsg.innerText?.trim() : null,
      bodyText: document.body.innerText.substring(0, 400)
    };
  });
  console.log('\nPOST-LOGIN DOM:', JSON.stringify(postLoginDOM, null, 2));

  // Check network requests that happened
  const loginNetworkReqs = networkLog.filter(n => n.dir === 'RES' &&
    (n.url.includes('/api/') || n.url.includes('supabase') || n.url.includes('auth') || n.url.includes('token'))
  );
  console.log('\nNETWORK during login:');
  loginNetworkReqs.forEach(r => {
    console.log(`  [${r.method}] ${r.url} -> ${r.status}`);
    if (r.body) console.log(`  BODY: ${r.body.substring(0, 500)}`);
  });

  // ═══════════════════════════════════════════════════════════
  console.log('\n══════════════════════════════════════════════');
  console.log('DEEP DIVE: HTML source analysis');
  console.log('══════════════════════════════════════════════');
  const fullHTML = await page.evaluate(() => document.documentElement.innerHTML);
  // Save HTML for analysis
  fs.writeFileSync('/Users/xxvirusxx/PY/Bots/lns_screenshots/page_source.html', fullHTML);
  console.log('HTML saved to lns_screenshots/page_source.html');
  console.log(`HTML length: ${fullHTML.length} chars`);

  // Search for auth-overlay handling
  const authOverlaySection = fullHTML.match(/auth-overlay[\s\S]{0,2000}/)?.[0] || 'NOT FOUND';
  console.log('\nauth-overlay in HTML:', authOverlaySection.substring(0, 1000));

  // Search for login function
  const loginFnMatch = fullHTML.match(/function\s+login[\s\S]{0,2000}/)?.[0] || fullHTML.match(/loginUser[\s\S]{0,2000}/)?.[0] || 'NOT FOUND';
  console.log('\nLogin function in HTML:', loginFnMatch.substring(0, 1000));

  // ═══════════════════════════════════════════════════════════
  console.log('\n══════════════════════════════════════════════');
  console.log('STEP 4-10: Checking dashboard state & products');
  console.log('══════════════════════════════════════════════');

  // Check current state - is user logged in?
  const currentState = await page.evaluate(() => ({
    url: window.location.href,
    title: document.title,
    bodyText: document.body.innerText.substring(0, 800),
    hasAuthOverlay: !!document.getElementById('auth-overlay'),
    authOverlayClass: document.getElementById('auth-overlay')?.className,
    authOverlayDisplay: document.getElementById('auth-overlay') ?
      window.getComputedStyle(document.getElementById('auth-overlay')).display : 'N/A'
  }));
  console.log('CURRENT STATE:', JSON.stringify(currentState, null, 2));

  await shot(page, '04_current_state');

  // ─── Try with Supabase direct API call to understand what backend expects ─
  console.log('\n══════════════════════════════════════════════');
  console.log('TESTING: Extract Supabase config from page');
  console.log('══════════════════════════════════════════════');
  const supabaseConfig = await page.evaluate(() => {
    // Look for supabase key/url in global variables
    const scripts = Array.from(document.querySelectorAll('script')).map(s => s.textContent?.substring(0, 500)).filter(t => t && (t.includes('supabase') || t.includes('SUPABASE')));
    const globalSupabase = window.supabase || window._supabase || window.SUPABASE_URL;
    const globalKeys = Object.keys(window).filter(k => k.toLowerCase().includes('supabase') || k.toLowerCase().includes('anon'));

    // Check meta tags
    const metas = Array.from(document.querySelectorAll('meta')).map(m => ({ name: m.name, content: m.content?.substring(0, 100) }));

    return {
      scripts: scripts.slice(0, 5),
      globalKeys,
      metas: metas.filter(m => m.name || m.content)
    };
  });
  console.log('SUPABASE CONFIG:', JSON.stringify(supabaseConfig, null, 2));

  // ─── Scroll down to see products section ─────────────────────────────────
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(500);
  await page.evaluate(() => window.scrollTo(0, 2000));
  await sleep(1000);
  await shot(page, '05_products_section');

  const productCards = await page.evaluate(() => {
    const cards = document.querySelectorAll('[class*="card" i], [class*="product" i], .bot-card, .product-card, [data-product]');
    return Array.from(cards).slice(0, 10).map(el => ({
      class: el.className.substring(0,80),
      id: el.id,
      text: el.innerText?.trim().substring(0, 100),
      rect: el.getBoundingClientRect(),
      hasClick: el.onclick ? 'yes' : 'no',
      dataset: JSON.stringify(el.dataset)
    }));
  });
  console.log('\nPRODUCT CARDS:', JSON.stringify(productCards, null, 2));

  // ─── See all products page ────────────────────────────────────────────────
  const seeAllLink = await page.locator('text=See All Products, a:has-text("All Products"), a:has-text("Products")').first();
  const seeAllCount = await seeAllLink.count();
  if (seeAllCount > 0) {
    const linkText = await seeAllLink.textContent();
    const linkHref = await seeAllLink.getAttribute('href');
    console.log(`\n"See All" link: "${linkText?.trim()}" -> ${linkHref}`);
    await seeAllLink.click();
    await sleep(2000);
    await shot(page, '05b_all_products_page');
    console.log(`URL after See All: ${page.url()}`);

    const allProductsText = await page.evaluate(() => document.body.innerText.substring(0, 600));
    console.log('Products page text:', allProductsText);
  }

  // ─── Look for Legal Notice on current page ────────────────────────────────
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(500);

  console.log('\n══════════════════════════════════════════════');
  console.log('STEP 6: Find and click Legal Notice');
  console.log('══════════════════════════════════════════════');

  const legalLocator = page.locator('text=Legal Notice').first();
  const legalCount = await legalLocator.count();
  if (legalCount > 0) {
    // Check if auth overlay might block it
    const overlayCheck = await page.evaluate(() => {
      const overlay = document.getElementById('auth-overlay');
      return overlay ? {
        class: overlay.className,
        display: window.getComputedStyle(overlay).display,
        zIndex: window.getComputedStyle(overlay).zIndex,
        pointerEvents: window.getComputedStyle(overlay).pointerEvents
      } : null;
    });
    console.log('Auth overlay before click:', JSON.stringify(overlayCheck));

    // Try clicking via JavaScript to bypass overlay
    const clickResult2 = await page.evaluate(() => {
      const el = Array.from(document.querySelectorAll('*')).find(el =>
        el.innerText?.trim() === 'Legal Notice' && el.tagName !== 'HTML' && el.tagName !== 'BODY'
      );
      if (!el) return { error: 'Not found' };
      el.click();
      return { clicked: el.tagName + '/' + el.className.substring(0,40) + '/' + el.innerText?.trim().substring(0,30) };
    });
    console.log('Legal Notice JS click:', JSON.stringify(clickResult2));
    await sleep(2000);
    await shot(page, '06_after_legal_click');

    const afterClickState = await page.evaluate(() => ({
      url: window.location.href,
      overlayClass: document.getElementById('auth-overlay')?.className,
      modalClass: document.querySelector('.modal')?.className,
      bodyText: document.body.innerText.substring(0, 500),
      panelVisible: (() => {
        const panels = document.querySelectorAll('[class*="panel" i], [class*="drawer" i], [class*="detail" i]');
        return Array.from(panels).filter(el => window.getComputedStyle(el).display !== 'none' && el.getBoundingClientRect().width > 0).map(el => ({ class: el.className.substring(0,60), text: el.innerText?.trim().substring(0,100) }));
      })()
    }));
    console.log('After Legal Notice click:', JSON.stringify(afterClickState, null, 2));
  } else {
    console.log('Legal Notice NOT FOUND on current page');
    const pageText = await page.evaluate(() => document.body.innerText.substring(0, 800));
    console.log('Current page text:', pageText);
  }

  // ─── Step 7: Find textarea ────────────────────────────────────────────────
  console.log('\n══════════════════════════════════════════════');
  console.log('STEP 7: Find textarea and run');
  console.log('══════════════════════════════════════════════');

  const textareaCheck = await page.evaluate(() => {
    const textareas = document.querySelectorAll('textarea');
    return Array.from(textareas).map(el => ({
      id: el.id,
      class: el.className,
      placeholder: el.placeholder,
      display: window.getComputedStyle(el).display,
      visibility: window.getComputedStyle(el).visibility,
      rect: el.getBoundingClientRect()
    }));
  });
  console.log('TEXTAREAS:', JSON.stringify(textareaCheck, null, 2));

  // ─── Step 10: Google button ───────────────────────────────────────────────
  console.log('\n══════════════════════════════════════════════');
  console.log('STEP 10: Continue with Google');
  console.log('══════════════════════════════════════════════');

  await page.goto('https://lnsbotz.latenightstack.com', { waitUntil: 'networkidle', timeout: 20000 });
  await sleep(1000);
  await page.locator('text=Get Started').first().click();
  await sleep(1500);
  await shot(page, '10a_modal_google');

  // Find Google button in modal
  const googleInfo = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button, a')).filter(el =>
      el.innerText?.includes('Google') || el.className?.includes('google') || el.id?.includes('google')
    );
    return btns.map(el => ({
      tag: el.tagName,
      id: el.id,
      class: el.className.substring(0,60),
      text: el.innerText?.trim(),
      href: el.href,
      onclick: el.getAttribute('onclick'),
      display: window.getComputedStyle(el).display,
      rect: el.getBoundingClientRect()
    }));
  });
  console.log('GOOGLE BUTTONS:', JSON.stringify(googleInfo, null, 2));

  if (googleInfo.length > 0) {
    // Clear network log
    const preGoogleNetworkLen = networkLog.length;

    // Click Google button via JS
    const googleClickResult = await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('button, a')).find(el =>
        el.innerText?.includes('Google')
      );
      if (!btn) return { error: 'Not found' };
      btn.click();
      return { clicked: btn.id + '/' + btn.className.substring(0,40) };
    });
    console.log('Google click result:', JSON.stringify(googleClickResult));

    await sleep(3000);
    await shot(page, '10b_after_google');
    console.log(`URL after Google: ${page.url()}`);

    // Network after Google click
    const googleNetwork = networkLog.slice(preGoogleNetworkLen).filter(n => n.dir === 'RES');
    console.log('\nNETWORK after Google click:');
    googleNetwork.forEach(r => {
      console.log(`  [${r.method}] ${r.url} -> ${r.status}`);
      if (r.body && r.body.trim()) console.log(`  BODY: ${r.body.substring(0, 300)}`);
    });
  }

  // ═══════════════════════════════════════════════════════════
  console.log('\n══════════════════════════════════════════════');
  console.log('FULL CONSOLE LOG');
  console.log('══════════════════════════════════════════════');
  const errors = consoleLog.filter(e => e.type === 'error' || e.type === 'pageerror');
  const warnings = consoleLog.filter(e => e.type === 'warn');
  console.log(`Total errors: ${errors.length}, warnings: ${warnings.length}`);
  errors.forEach(e => console.log(`  [ERROR] ${e.text}`));
  warnings.forEach(e => console.log(`  [WARN] ${e.text}`));

  console.log('\n══════════════════════════════════════════════');
  console.log('FULL NETWORK LOG (API/Auth calls only)');
  console.log('══════════════════════════════════════════════');
  const apiCalls = networkLog.filter(n => n.dir === 'RES' &&
    (n.url.includes('/api/') || n.url.includes('supabase') || n.url.includes('/auth') || n.url.includes('token') || n.url.includes('.ai/'))
  );
  console.log(`Total API/auth calls: ${apiCalls.length}`);
  apiCalls.forEach(r => {
    console.log(`[${r.method}] ${r.url} -> ${r.status}`);
    if (r.body) console.log(`  ${r.body.substring(0, 800)}`);
  });

  await browser.close();
  console.log('\nDone. Screenshots in:', SCREENSHOTS_DIR);
})();
