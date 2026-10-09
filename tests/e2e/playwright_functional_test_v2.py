"""
LateNightStack - Complete Functional Test via Playwright (v2 - corrected selectors)
"""
import asyncio
import os
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:8000"
SCREENSHOT_DIR = "/Users/xxvirusxx/PY/Bots/tests/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

results = []

def report(num, name, passed, detail):
    status = "PASS" if passed else "FAIL"
    results.append((num, name, status, detail))
    print(f"[{status}] Test {num}: {name} — {detail}")


async def run_tests():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Collect console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page_errors = []
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        # ── TEST 1: Landing page loads ─────────────────────────────────────
        try:
            response = await page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
            status_code = response.status if response else None
            title = await page.title()
            # Give JS a moment to execute
            await page.wait_for_timeout(500)
            js_errs = [e for e in console_errors if "setAttribute" in e or "null" in e]
            if response and response.ok:
                if page_errors or js_errs:
                    report(1, "Landing page loads", False,
                           f"HTTP {status_code}, title='{title}', JS error: {(page_errors + js_errs)[0][:120]}")
                else:
                    report(1, "Landing page loads", True,
                           f"HTTP {status_code}, title='{title}', no JS errors")
            else:
                report(1, "Landing page loads", False, f"HTTP {status_code}")
        except Exception as e:
            report(1, "Landing page loads", False, str(e)[:150])

        await page.screenshot(path=f"{SCREENSHOT_DIR}/01_landing.png", full_page=False)

        # ── TEST 2: Floating pill nav ──────────────────────────────────────
        try:
            nav = page.locator("nav").first
            await nav.wait_for(state="visible", timeout=5000)
            nav_text = await nav.inner_text()
            expected = ["LateNightStack", "Products", "Pricing", "Telegram", "Get Started"]
            found = [e for e in expected if e in nav_text]
            found_all = len(found) == len(expected)

            # Check computed style — is it floating (fixed/sticky/absolute)?
            nav_position = await nav.evaluate("el => window.getComputedStyle(el).position")
            # Also check parent wrapper
            wrapper = page.locator("header, .nav-wrapper, .navbar-wrapper, [class*='nav-wrap']").first
            wrapper_pos = "n/a"
            if await wrapper.count() > 0:
                wrapper_pos = await wrapper.evaluate("el => window.getComputedStyle(el).position")

            pill_style = await page.evaluate("""() => {
                const nav = document.querySelector('nav');
                if (!nav) return 'no nav';
                const s = window.getComputedStyle(nav);
                return `position:${s.position} borderRadius:${s.borderRadius} bg:${s.background.substring(0,30)}`;
            }""")

            report(2, "Floating pill nav", found_all,
                   f"Labels found: {found} ({len(found)}/{len(expected)}); pill style: {pill_style[:100]}")
        except Exception as e:
            report(2, "Floating pill nav", False, str(e)[:150])

        # ── TEST 3: Particle animation ─────────────────────────────────────
        try:
            canvas_count = await page.locator("canvas").count()
            particle_containers = await page.locator(
                "#particles-js, #tsparticles, [id*='particle'], [class*='particle']"
            ).count()
            found = canvas_count > 0 or particle_containers > 0
            report(3, "Particle animation", found,
                   f"canvas={canvas_count}, particle containers={particle_containers}")
        except Exception as e:
            report(3, "Particle animation", False, str(e)[:150])

        # ── TEST 4: Hero section headline & glow orb ──────────────────────
        try:
            # Use JS to get text content (handles <br> as space)
            hero_h1 = await page.evaluate("""() => {
                const h1 = document.querySelector('.hero h1');
                return h1 ? h1.textContent.replace(/\\s+/g,' ').trim() : 'NOT FOUND';
            }""")
            orb_count = await page.locator(".hero-orb, [class*='orb'], [class*='glow-orb']").count()
            headline_ok = "Turn AI Into" in hero_h1 and "Passive Income" in hero_h1
            report(4, "Hero section", headline_ok,
                   f"h1 text='{hero_h1}'; orb elements={orb_count}")
        except Exception as e:
            report(4, "Hero section", False, str(e)[:150])

        # ── TEST 5: Register modal ─────────────────────────────────────────
        try:
            # Click the nav "Get Started" button
            get_started = page.locator("button.nav-cta-btn, button:has-text('Get Started')").first
            await get_started.scroll_into_view_if_needed()
            await get_started.click()
            await page.wait_for_timeout(800)

            # Check overlay has .open class
            overlay = page.locator("#auth-overlay")
            has_open = await overlay.evaluate("el => el.classList.contains('open')")
            overlay_display = await overlay.evaluate("el => window.getComputedStyle(el).display")

            # Check tabs
            login_tab = page.locator("#tab-l")
            signup_tab = page.locator("#tab-r")
            login_text = await login_tab.inner_text() if await login_tab.count() > 0 else ""
            signup_text = await signup_tab.inner_text() if await signup_tab.count() > 0 else ""

            modal_ok = has_open and "Login" in login_text and "Sign Up" in signup_text
            report(5, "Register modal", modal_ok,
                   f"overlay.open={has_open}, display={overlay_display}, Login tab='{login_text}', SignUp tab='{signup_text}'")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/05_modal.png")
        except Exception as e:
            report(5, "Register modal", False, str(e)[:150])
            await page.screenshot(path=f"{SCREENSHOT_DIR}/05_modal_error.png")

        # ── TEST 6: Register a new user ────────────────────────────────────
        try:
            # Make sure modal is open — re-open if needed
            overlay = page.locator("#auth-overlay")
            is_open = await overlay.evaluate("el => el.classList.contains('open')")
            if not is_open:
                await page.locator("button.nav-cta-btn").first.click()
                await page.wait_for_timeout(500)

            # Switch to Sign Up tab
            await page.locator("#tab-r").click()
            await page.wait_for_timeout(300)

            # Fill the registration form (fields are in the register section)
            name_field = page.locator("#r-name, input[id*='name'][id*='r'], input[placeholder*='name' i]").first
            email_field = page.locator("#r-email, input[id='r-email']").first
            pass_field = page.locator("#r-pass, input[id='r-pass']").first

            # Fallback: all visible inputs
            if await name_field.count() == 0 or not await name_field.is_visible():
                name_field = page.locator("input[placeholder*='Name'], input[placeholder*='name']").first

            await name_field.fill("Test User")
            await email_field.fill("test123@gmail.com")
            await pass_field.fill("TestPass123")

            await page.screenshot(path=f"{SCREENSHOT_DIR}/06_before_register.png")

            # Click submit
            submit_btn = page.locator("#r-btn, button:has-text('Create Free Account'), button:has-text('Sign Up')").first
            await submit_btn.click()
            await page.wait_for_timeout(3000)

            # Check result
            body_text = await page.locator("body").inner_text()
            success = any(w.lower() in body_text.lower() for w in ["welcome", "dashboard", "logged in", "account created"])
            # Also check for inline error message
            err_el = await page.locator("#r-msg, #msg, .msg-error, [class*='msg']").count()
            err_text = await page.locator("#r-msg, #msg").first.inner_text() if err_el > 0 else ""

            await page.screenshot(path=f"{SCREENSHOT_DIR}/06_after_register.png")
            report(6, "Register new user", success,
                   f"Success={success}; error msg='{err_text[:80] or 'none'}'")
        except Exception as e:
            report(6, "Register new user", False, str(e)[:200])
            await page.screenshot(path=f"{SCREENSHOT_DIR}/06_error.png")

        # ── TEST 7: Login ──────────────────────────────────────────────────
        try:
            # Re-open if closed, switch to Login tab
            overlay = page.locator("#auth-overlay")
            is_open = await overlay.evaluate("el => el.classList.contains('open')") if await overlay.count() > 0 else False
            if not is_open:
                await page.locator("button.nav-cta-btn").first.click()
                await page.wait_for_timeout(500)

            await page.locator("#tab-l").click()
            await page.wait_for_timeout(300)

            email_field = page.locator("#l-email")
            pass_field = page.locator("#l-pass")
            await email_field.fill("test123@gmail.com")
            await pass_field.fill("TestPass123")

            await page.screenshot(path=f"{SCREENSHOT_DIR}/07_before_login.png")

            login_btn = page.locator("#l-btn, button:has-text('Login'), button:has-text('Sign In')").first
            await login_btn.click()
            await page.wait_for_timeout(2500)

            body_text = await page.locator("body").inner_text()
            logged_in = any(w.lower() in body_text.lower() for w in ["welcome back", "dashboard", "logout"])

            await page.screenshot(path=f"{SCREENSHOT_DIR}/07_after_login.png")
            report(7, "Login", logged_in, f"Logged-in indicators found={logged_in}")
        except Exception as e:
            report(7, "Login", False, str(e)[:200])

        # ── TEST 8: Dashboard appears ──────────────────────────────────────
        try:
            # Check for dashboard section
            dashboard = page.locator("#user-dashboard, #dashboard, [class*='dashboard']").first
            dash_visible = await dashboard.is_visible() if await page.locator("#user-dashboard, #dashboard, [class*='dashboard']").count() > 0 else False
            dash_text = await dashboard.inner_text() if dash_visible else ""

            has_welcome = "welcome back" in dash_text.lower() or "welcome" in dash_text.lower()
            has_bots = any(w.lower() in dash_text.lower() for w in ["bot", "active", "total", "stat"])

            report(8, "Dashboard appears after login", dash_visible and has_welcome,
                   f"Dashboard visible={dash_visible}, 'welcome back'={has_welcome}, bot stats={has_bots}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/08_dashboard.png")
        except Exception as e:
            report(8, "Dashboard appears after login", False, str(e)[:150])

        # ── TEST 9: Scroll to Features ─────────────────────────────────────
        try:
            # Scroll to features section
            features_section = page.locator("#features, [id='features'], section:has-text('Intelligence')").first
            if await features_section.count() > 0:
                await features_section.scroll_into_view_if_needed()
            else:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.35)")
            await page.wait_for_timeout(800)

            page_text = await page.locator("body").inner_text()
            feature_cards = ["Intelligence", "Content", "Document", "Political", "Multilingual", "Real Estate"]
            found_cards = [f for f in feature_cards if f in page_text]

            report(9, "Scroll to Features", len(found_cards) == 6,
                   f"Found {len(found_cards)}/6: {found_cards}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/09_features.png")
        except Exception as e:
            report(9, "Scroll to Features", False, str(e)[:150])

        # ── TEST 10: Interstitial glow ─────────────────────────────────────
        try:
            tagline_el = page.locator("h2:has-text('bots work'), h2:has-text('while you sleep'), section:has-text('bots work')").first
            tagline_text = await page.evaluate("""() => {
                const h2s = document.querySelectorAll('h2');
                for (const h of h2s) {
                    const t = h.textContent.replace(/\\s+/g,' ').trim();
                    if (t.includes('bots work') || t.includes('sleep')) return t;
                }
                return 'NOT FOUND';
            }""")
            tagline_found = "bots work" in tagline_text.lower() or "sleep" in tagline_text.lower()
            glow_el = await page.locator("[class*='interstitial'], [class*='glow-bg'], [class*='sleep']").count()

            report(10, "Interstitial glow", tagline_found,
                   f"Tagline text='{tagline_text}'; glow elements={glow_el}")
        except Exception as e:
            report(10, "Interstitial glow", False, str(e)[:150])

        # ── TEST 11: Telegram section ──────────────────────────────────────
        try:
            tg_section = page.locator("#telegram, [id='telegram'], section:has-text('EzAeyebot')").first
            if await tg_section.count() > 0:
                await tg_section.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)

            page_text = await page.locator("body").inner_text()
            has_bot = "@EzAeyebot" in page_text or "EzAeyebot" in page_text
            chat_el = await page.locator("[class*='chat'], [class*='telegram-mock'], [class*='chat-mock']").count()

            report(11, "Telegram section", has_bot,
                   f"@EzAeyebot found={has_bot}, chat/mock elements={chat_el}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/11_telegram.png")
        except Exception as e:
            report(11, "Telegram section", False, str(e)[:150])

        # ── TEST 12: Pricing section ───────────────────────────────────────
        try:
            pricing_section = page.locator("#pricing, [id='pricing']").first
            if await pricing_section.count() > 0:
                await pricing_section.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)

            page_text = await page.locator("body").inner_text()
            plans = ["Free", "Starter", "Pro", "Business"]
            found_plans = [p for p in plans if p in page_text]

            # Check Pro card highlighted with glow/border
            pro_glow = await page.evaluate("""() => {
                const cards = document.querySelectorAll('[class*="plan"], [class*="pricing-card"], .plan');
                for (const c of cards) {
                    if (c.textContent.includes('Pro') && !c.textContent.includes('Business')) {
                        const s = window.getComputedStyle(c);
                        return `border:${s.border.substring(0,40)} boxShadow:${s.boxShadow.substring(0,60)}`;
                    }
                }
                return 'Pro card not found';
            }""")

            report(12, "Pricing section", len(found_plans) == 4,
                   f"{len(found_plans)}/4 plans: {found_plans}; Pro style: {pro_glow[:100]}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/12_pricing.png")
        except Exception as e:
            report(12, "Pricing section", False, str(e)[:150])

        # ── TEST 13: PayPal buttons ────────────────────────────────────────
        try:
            # PayPal buttons may be iframes or rendered divs
            paypal_el = await page.locator(
                "[id*='paypal'], [class*='paypal'], iframe[src*='paypal'], .paypal-btn, [data-paypal]"
            ).count()
            # Check for "or pay with" text
            page_text = await page.locator("body").inner_text()
            has_separator = "or pay with" in page_text.lower()
            paypal_text = "paypal" in page_text.lower()

            report(13, "PayPal buttons", paypal_el > 0 or has_separator,
                   f"PayPal elements={paypal_el}, 'or pay with' separator={has_separator}, PayPal text={paypal_text}")
        except Exception as e:
            report(13, "PayPal buttons", False, str(e)[:150])

        # ── TEST 14: CTA closer ────────────────────────────────────────────
        try:
            closer = page.locator(".closer, #closer, [class*='cta-closer']").first
            if await closer.count() > 0:
                await closer.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)

            cta_text = await page.evaluate("""() => {
                const el = document.querySelector('.closer h2');
                return el ? el.textContent.replace(/\\s+/g,' ').trim() : 'NOT FOUND';
            }""")
            rings_el = await page.locator(".closer::before, [class*='ring'], .closer").count()
            cta_ok = "Start building on" in cta_text and "LateNightStack" in cta_text

            report(14, "CTA closer", cta_ok,
                   f"CTA h2='{cta_text}'; .closer elements={rings_el}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/14_cta.png")
        except Exception as e:
            report(14, "CTA closer", False, str(e)[:150])

        # ── TEST 15: Footer ────────────────────────────────────────────────
        try:
            footer = page.locator("footer").first
            if await footer.count() > 0:
                await footer.scroll_into_view_if_needed()
                await page.wait_for_timeout(400)

            footer_visible = await footer.is_visible() if await footer.count() > 0 else False
            footer_text = await footer.inner_text() if footer_visible else ""
            has_india = "India" in footer_text or "🇮🇳" in footer_text
            link_count = await page.locator("footer a").count()

            report(15, "Footer", footer_visible and (has_india or link_count > 0),
                   f"visible={footer_visible}, 'Built in India'={has_india}, links={link_count}")
        except Exception as e:
            report(15, "Footer", False, str(e)[:150])

        # ── Final full-page screenshot ─────────────────────────────────────
        try:
            await page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(1500)
            await page.screenshot(path=f"{SCREENSHOT_DIR}/final_fullpage.png", full_page=True)
            print(f"\nFull-page screenshot: {SCREENSHOT_DIR}/final_fullpage.png")
            # Also take viewport screenshot at top
            await page.screenshot(path=f"{SCREENSHOT_DIR}/final_viewport.png", full_page=False)
        except Exception as e:
            print(f"Screenshot error: {e}")

        await browser.close()

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("FUNCTIONAL TEST SUMMARY — LateNightStack http://localhost:8000")
    print("="*70)
    passed = sum(1 for r in results if r[2] == "PASS")
    failed = sum(1 for r in results if r[2] == "FAIL")
    for num, name, status, detail in results:
        icon = "PASS" if status == "PASS" else "FAIL"
        print(f"  [{icon}] #{num:02d} {name}")
        print(f"        {detail}")
    print(f"\n  Total: {passed} PASS / {failed} FAIL out of {len(results)} tests")
    print("="*70)


asyncio.run(run_tests())
