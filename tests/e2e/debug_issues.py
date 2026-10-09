"""
Debug script for:
  Issue 1: UI breaks after login
  Issue 2: Products API not accessible
"""
import asyncio
import json
import os
import re
import base64
from playwright.async_api import async_playwright

SCREENSHOT_DIR = '/Users/xxvirusxx/PY/Bots/lns_screenshots'
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

console_errors = []
network_errors = []
auth_token = None


def save_ss(name):
    return os.path.join(SCREENSHOT_DIR, f'debug_{name}.png')


async def main():
    global auth_token

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # ─────────────────────────────────────────────────────────────────────
        # ISSUE 1: UI AFTER LOGIN
        # ─────────────────────────────────────────────────────────────────────
        print('\n' + '='*60)
        print('ISSUE 1: UI AFTER LOGIN')
        print('='*60)

        ctx = await browser.new_context(
            viewport={'width': 1280, 'height': 900},
            java_script_enabled=True,
        )
        page = await ctx.new_page()

        def on_console(msg):
            t = msg.type
            text = msg.text
            if t in ('error', 'warning'):
                console_errors.append(f'[{t.upper()}] {text}')
            print(f'  CONSOLE [{t}]: {text}')

        def on_request_failed(req):
            err = req.failure
            msg = f'FAILED: {req.method} {req.url} — {err}'
            network_errors.append(msg)
            print(f'  NET FAIL: {msg}')

        api_responses = []

        async def on_response(resp):
            url = resp.url
            status = resp.status
            if '/api/' in url or 'lnsbotz' in url:
                print(f'  RESPONSE: {resp.request.method} {url} → {status}')
                api_responses.append({'method': resp.request.method, 'url': url, 'status': status})

        page.on('console', on_console)
        page.on('requestfailed', on_request_failed)
        page.on('response', on_response)

        # Step 1: Load homepage
        print('\n[STEP 1] Loading homepage...')
        await page.goto('https://lnsbotz.latenightstack.com', wait_until='networkidle', timeout=30000)
        await page.screenshot(path=save_ss('01_homepage'), full_page=False)
        print(f'  URL: {page.url}')
        print(f'  Title: {await page.title()}')
        print('  Screenshot: debug_01_homepage.png')

        # Step 2: Click Get Started
        print('\n[STEP 2] Clicking Get Started...')
        try:
            btn = page.locator('text=Get Started').first
            await btn.wait_for(timeout=10000)
            await btn.click()
            await page.wait_for_timeout(1500)
            await page.screenshot(path=save_ss('02_modal_open'), full_page=False)
            print('  Screenshot: debug_02_modal_open.png')
        except Exception as e:
            print(f'  ERROR: {e}')
            await page.screenshot(path=save_ss('02_fail'), full_page=True)

        # Step 3: Click Sign In / Login tab
        print('\n[STEP 3] Switching to login tab...')
        for selector in ['text=Sign In', 'text=Login', '[role="tab"]:has-text("Sign In")', '[role="tab"]:has-text("Login")']:
            try:
                el = page.locator(selector).first
                await el.wait_for(timeout=3000)
                await el.click()
                print(f'  Clicked: {selector}')
                await page.wait_for_timeout(500)
                break
            except Exception:
                pass

        await page.screenshot(path=save_ss('03_login_tab'), full_page=False)

        # Step 4: Fill login form
        print('\n[STEP 4] Filling login form...')
        try:
            email_field = page.locator('input[type="email"], input[name="email"]').first
            await email_field.wait_for(timeout=8000)
            await email_field.fill('prabhat@lnsbotz.ai')

            pw_field = page.locator('input[type="password"]').first
            await pw_field.fill(os.environ['LNS_TEST_PASSWORD'])
            print('  Filled email + password')
            await page.screenshot(path=save_ss('04_login_filled'), full_page=False)
        except Exception as e:
            print(f'  ERROR: {e}')
            await page.screenshot(path=save_ss('04_fail'), full_page=True)

        # Step 5: Submit login
        print('\n[STEP 5] Submitting login...')
        login_response_body = None
        try:
            # Set up response interceptor for login API
            login_future = asyncio.get_event_loop().create_future()

            async def capture_login_response(resp):
                url = resp.url.lower()
                if resp.request.method == 'POST' and any(k in url for k in ['/login', '/auth', '/token', '/signin']):
                    try:
                        body = await resp.json()
                        if not login_future.done():
                            login_future.set_result(body)
                    except Exception:
                        pass

            page.on('response', capture_login_response)

            submit_btn = page.locator('button[type="submit"], button:has-text("Sign In"), button:has-text("Login"), button:has-text("Log In")').first
            await submit_btn.wait_for(timeout=8000)
            await submit_btn.click()
            print('  Clicked submit')

            # Wait for navigation or timeout
            try:
                await asyncio.wait_for(asyncio.shield(login_future), timeout=10.0)
                login_response_body = login_future.result()
                print(f'  Login API response: {json.dumps(login_response_body)[:500]}')
                auth_token = (
                    login_response_body.get('access_token') or
                    login_response_body.get('token') or
                    (login_response_body.get('data') or {}).get('token') or
                    (login_response_body.get('data') or {}).get('access_token')
                )
                if auth_token:
                    print(f'  Token captured: {auth_token[:40]}...')
            except asyncio.TimeoutError:
                print('  No login API response intercepted within timeout')

            await page.wait_for_timeout(4000)
            current_url = page.url
            print(f'  Current URL after login: {current_url}')

        except Exception as e:
            print(f'  ERROR: {e}')

        # Take screenshots immediately after login
        await page.screenshot(path=save_ss('05_after_login'), full_page=False)
        await page.screenshot(path=save_ss('05_after_login_full'), full_page=True)
        print('  Screenshots: debug_05_after_login.png (viewport) + debug_05_after_login_full.png (full)')

        # Step 6: Layout inspection
        print('\n[STEP 6] Inspecting DOM layout...')
        try:
            layout_info = await page.evaluate('''() => {
                const results = {};
                const body = document.body;
                const bodyStyle = window.getComputedStyle(body);
                results.body = {
                    overflow: bodyStyle.overflow,
                    overflowX: bodyStyle.overflowX,
                    overflowY: bodyStyle.overflowY,
                    scrollHeight: body.scrollHeight,
                    scrollWidth: body.scrollWidth,
                };
                // Nav
                const nav = document.querySelector("nav, header, [class*='nav'], [class*='header']");
                if (nav) {
                    const s = window.getComputedStyle(nav);
                    results.nav = {
                        tag: nav.tagName, classes: nav.className.toString().substring(0, 100),
                        position: s.position, zIndex: s.zIndex, top: s.top,
                        height: nav.offsetHeight, display: s.display,
                    };
                }
                // Hero
                const hero = document.querySelector("[class*='hero'],[class*='Hero'],section:first-of-type,.hero");
                if (hero) {
                    const s = window.getComputedStyle(hero);
                    results.hero = {
                        classes: hero.className.toString().substring(0, 100),
                        position: s.position, zIndex: s.zIndex,
                        marginTop: s.marginTop, paddingTop: s.paddingTop,
                        height: hero.offsetHeight, top: hero.getBoundingClientRect().top,
                    };
                }
                // Dashboard / main
                const main = document.querySelector("main,[class*='dashboard'],[class*='Dashboard'],[id*='dashboard']");
                if (main) {
                    const s = window.getComputedStyle(main);
                    results.main = {
                        tag: main.tagName, classes: main.className.toString().substring(0, 100),
                        position: s.position, zIndex: s.zIndex,
                        marginTop: s.marginTop, paddingTop: s.paddingTop,
                        height: main.offsetHeight, top: main.getBoundingClientRect().top,
                    };
                }
                // Any open modals
                const modals = Array.from(document.querySelectorAll("[class*='modal'],[class*='Modal'],[role='dialog']"));
                results.openModals = modals.filter(m => {
                    const s = window.getComputedStyle(m);
                    return s.display !== "none" && s.visibility !== "hidden" && parseFloat(s.opacity) > 0;
                }).map(m => ({ classes: m.className.toString().substring(0, 80), zIndex: window.getComputedStyle(m).zIndex }));
                // Elements at top of viewport
                results.topElements = [];
                for (let x = 100; x <= 1100; x += 200) {
                    const el = document.elementFromPoint(x, 100);
                    if (el) results.topElements.push({x, tag: el.tagName, classes: el.className.toString().substring(0, 80)});
                }
                results.pageTitle = document.title;
                results.h1s = Array.from(document.querySelectorAll("h1")).map(h => h.textContent.trim()).slice(0, 5);
                results.visibleText = document.body.innerText.substring(0, 800);
                // Storage for token
                const lsKeys = Object.keys(localStorage);
                const ssKeys = Object.keys(sessionStorage);
                results.storageKeys = {localStorage: lsKeys, sessionStorage: ssKeys};
                for (const k of lsKeys) {
                    const v = localStorage.getItem(k);
                    if (v && (v.includes("eyJ") || k.toLowerCase().includes("token") || k.toLowerCase().includes("auth"))) {
                        results.tokenInStorage = `localStorage[${k}] (${v.length} chars): ${v.substring(0, 120)}`;
                        break;
                    }
                }
                for (const k of lsKeys) {
                    try {
                        const v = JSON.parse(localStorage.getItem(k));
                        const t = (v && (v.access_token || v.token || (v.data && v.data.token)));
                        if (t) { results.tokenNested = `localStorage[${k}].token = ${t.substring(0, 80)}`; break; }
                    } catch(e) {}
                }
                results.cookies = document.cookie.substring(0, 300);
                // All visible top-level DOM sections
                results.sections = Array.from(document.querySelectorAll("section, div[class*='section'], article")).slice(0, 10)
                    .map(el => ({ tag: el.tagName, classes: el.className.toString().substring(0, 80), height: el.offsetHeight, top: el.getBoundingClientRect().top }));
                return results;
            }''')
            print('\n  LAYOUT INSPECTION:')
            print(json.dumps(layout_info, indent=2))

            # Try to extract token from storage
            if not auth_token:
                for key in ['tokenInStorage', 'tokenNested']:
                    val = layout_info.get(key, '')
                    if val:
                        m = re.search(r'eyJ[\w.-]+', val)
                        if m:
                            auth_token = m.group(0)
                            print(f'\n  Token from storage: {auth_token[:40]}...')
                            break

        except Exception as e:
            print(f'  ERROR: {e}')

        # Step 7: Z-index & overflow inspection
        print('\n[STEP 7] Z-index and overflow check...')
        try:
            css_issues = await page.evaluate('''() => {
                const highZIndex = [];
                const allEls = document.querySelectorAll("*");
                for (const el of allEls) {
                    const s = window.getComputedStyle(el);
                    const z = parseInt(s.zIndex);
                    if (!isNaN(z) && z > 10) {
                        highZIndex.push({tag: el.tagName, id: el.id, classes: el.className.toString().substring(0, 80), zIndex: z, position: s.position, display: s.display, height: el.offsetHeight });
                    }
                }
                highZIndex.sort((a,b) => b.zIndex - a.zIndex);
                return { highZIndex: highZIndex.slice(0, 20) };
            }''')
            print('  Z-INDEX > 10 (top 20):')
            print(json.dumps(css_issues['highZIndex'], indent=2))
        except Exception as e:
            print(f'  ERROR: {e}')

        # Check cookies
        cookies = await ctx.cookies()
        print('\n  COOKIES:')
        for c in cookies:
            print(f"    {c['name']}={str(c['value'])[:60]}  (domain={c['domain']})")

        await ctx.close()

        # ─────────────────────────────────────────────────────────────────────
        # ISSUE 2: PRODUCTS API
        # ─────────────────────────────────────────────────────────────────────
        print('\n\n' + '='*60)
        print('ISSUE 2: PRODUCTS API')
        print('='*60)

        ctx2 = await browser.new_context(viewport={'width': 1280, 'height': 900})
        page2 = await ctx2.new_page()

        # If we still have no token, try direct API login calls
        if not auth_token:
            print('\n[API] Trying direct API login calls...')
            login_endpoints = [
                'https://lnsbotz.latenightstack.com/api/v1/auth/login',
                'https://lnsbotz.latenightstack.com/api/v1/users/login',
                'https://lnsbotz.latenightstack.com/api/v1/login',
                'https://lnsbotz.latenightstack.com/api/auth/login',
            ]
            for endpoint in login_endpoints:
                try:
                    result = await page2.evaluate('''async ([endpoint, pw]) => {
                        const resp = await fetch(endpoint, {
                            method: "POST",
                            headers: {"Content-Type": "application/json"},
                            body: JSON.stringify({email: "prabhat@lnsbotz.ai", password: pw})
                        });
                        const body = await resp.text();
                        return {status: resp.status, body: body.substring(0, 500)};
                    }''', [endpoint, os.environ['LNS_TEST_PASSWORD']])
                    print(f'  {endpoint} → {result["status"]}: {result["body"][:300]}')
                    if result['status'] in (200, 201):
                        try:
                            data = json.loads(result['body'])
                            auth_token = data.get('access_token') or data.get('token') or (data.get('data') or {}).get('token')
                            if auth_token:
                                print(f'  Got token: {auth_token[:40]}...')
                                break
                        except Exception:
                            pass
                except Exception as e:
                    print(f'  ERROR: {e}')

        print(f'\n  Auth token for API calls: {"YES — " + auth_token[:40] + "..." if auth_token else "NO TOKEN"}')

        # Step B: GET /api/v1/products/catalog
        print('\n[STEP B] GET /api/v1/products/catalog...')
        try:
            result = await page2.evaluate('''async (token) => {
                const headers = {"Content-Type": "application/json"};
                if (token) headers["Authorization"] = "Bearer " + token;
                const resp = await fetch("https://lnsbotz.latenightstack.com/api/v1/products/catalog", {headers});
                const body = await resp.text();
                return {status: resp.status, body: body.substring(0, 2000)};
            }''', auth_token)
            print(f'  Status: {result["status"]}')
            print(f'  Body: {result["body"][:2000]}')
        except Exception as e:
            print(f'  ERROR: {e}')

        # Step C: POST /api/v1/products/document/analyze
        print('\n[STEP C] POST /api/v1/products/document/analyze...')
        try:
            result = await page2.evaluate('''async (token) => {
                const headers = {"Content-Type": "application/json"};
                if (token) headers["Authorization"] = "Bearer " + token;
                const payload = {
                    product: "legal_notice",
                    text: "You owe Rs 50000. Pay in 15 days or face court action under Section 138.",
                    output_language: "en"
                };
                const resp = await fetch("https://lnsbotz.latenightstack.com/api/v1/products/document/analyze", {
                    method: "POST", headers, body: JSON.stringify(payload)
                });
                const body = await resp.text();
                return {status: resp.status, body: body.substring(0, 3000)};
            }''', auth_token)
            print(f'  Status: {result["status"]}')
            print(f'  Body: {result["body"][:3000]}')
        except Exception as e:
            print(f'  ERROR: {e}')

        # Also try without token
        print('\n[STEP C2] POST /api/v1/products/document/analyze WITHOUT token...')
        try:
            result = await page2.evaluate('''async () => {
                const payload = {
                    product: "legal_notice",
                    text: "You owe Rs 50000. Pay in 15 days or face court action under Section 138.",
                    output_language: "en"
                };
                const resp = await fetch("https://lnsbotz.latenightstack.com/api/v1/products/document/analyze", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(payload)
                });
                const body = await resp.text();
                return {status: resp.status, body: body.substring(0, 1000)};
            }''')
            print(f'  Status: {result["status"]}')
            print(f'  Body: {result["body"][:1000]}')
        except Exception as e:
            print(f'  ERROR: {e}')

        # Step D: Check /docs
        print('\n[STEP D] Checking /docs...')
        try:
            await page2.goto('https://lnsbotz.latenightstack.com/docs', wait_until='networkidle', timeout=20000)
            await page2.wait_for_timeout(3000)
            await page2.screenshot(path=save_ss('06_docs'), full_page=True)
            print('  Screenshot: debug_06_docs.png')

            docs_content = await page2.evaluate('''() => {
                const paths = Array.from(document.querySelectorAll(".opblock-summary-path, [data-path]"))
                    .map(el => el.textContent.trim()).filter(t => t);
                const tags = Array.from(document.querySelectorAll(".opblock-tag, h2, h3"))
                    .map(el => el.textContent.trim()).filter(t => t);
                const operations = Array.from(document.querySelectorAll(".opblock"))
                    .slice(0, 50).map(op => {
                        const method = op.querySelector(".opblock-summary-method");
                        const path = op.querySelector(".opblock-summary-path");
                        return {
                            method: method ? method.textContent.trim() : "",
                            path: path ? path.textContent.trim() : ""
                        };
                    }).filter(o => o.path);
                return {
                    title: document.title,
                    paths: [...new Set(paths)].slice(0, 50),
                    tags: [...new Set(tags)].slice(0, 30),
                    operations: operations,
                    pageText: document.body.innerText.substring(0, 4000),
                };
            }''')
            print(f'  Title: {docs_content["title"]}')
            print(f'  Operations found ({len(docs_content["operations"])}):')
            for op in docs_content['operations']:
                print(f'    [{op["method"]}] {op["path"]}')
            print(f'\n  Tags/Sections: {docs_content["tags"][:20]}')
            # Check if product routes exist
            all_paths = ' '.join(docs_content['paths'] + [op['path'] for op in docs_content['operations']])
            has_products = 'product' in all_paths.lower() or 'catalog' in all_paths.lower()
            print(f'\n  Product routes visible in /docs: {"YES" if has_products else "NO"}')
            print(f'\n  Page text (first 3000 chars):\n{docs_content["pageText"][:3000]}')
        except Exception as e:
            print(f'  ERROR: {e}')

        # Step E: Try other API root endpoints
        print('\n[STEP E] Probing API root...')
        probe_endpoints = [
            ('GET', 'https://lnsbotz.latenightstack.com/api/v1/'),
            ('GET', 'https://lnsbotz.latenightstack.com/api/'),
            ('GET', 'https://lnsbotz.latenightstack.com/openapi.json'),
            ('GET', 'https://lnsbotz.latenightstack.com/api/v1/health'),
            ('GET', 'https://lnsbotz.latenightstack.com/api/v1/products'),
        ]
        for method, url in probe_endpoints:
            try:
                result = await page2.evaluate('''async ({method, url, token}) => {
                    const headers = {"Content-Type": "application/json"};
                    if (token) headers["Authorization"] = "Bearer " + token;
                    const resp = await fetch(url, {method, headers});
                    const body = await resp.text();
                    return {status: resp.status, body: body.substring(0, 400)};
                }''', {'method': method, 'url': url, 'token': auth_token})
                print(f'  {method} {url} → {result["status"]}: {result["body"][:250]}')
            except Exception as e:
                print(f'  ERROR {method} {url}: {e}')

        await ctx2.close()
        await browser.close()

        print('\n\n' + '='*60)
        print('COLLECTED CONSOLE ERRORS:')
        if console_errors:
            for e in console_errors:
                print(f'  {e}')
        else:
            print('  (none)')

        print('\nCOLLECTED NETWORK FAILURES:')
        if network_errors:
            for e in network_errors:
                print(f'  {e}')
        else:
            print('  (none)')

        print('\nScreenshots saved to:', SCREENSHOT_DIR)


asyncio.run(main())
