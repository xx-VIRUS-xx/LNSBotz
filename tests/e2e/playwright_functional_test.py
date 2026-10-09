"""
LateNightStack - Complete Functional Test via Playwright
"""
import asyncio
import os
from playwright.async_api import async_playwright, expect

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
        page.on("console", lambda msg: console_errors.append(msg) if msg.type == "error" else None)
        page_errors = []
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        # ── TEST 1: Landing page loads ─────────────────────────────────────
        try:
            response = await page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
            status_code = response.status if response else None
            title = await page.title()
            if response and response.ok and not page_errors:
                report(1, "Landing page loads", True,
                       f"HTTP {status_code}, title='{title}', no JS errors")
            else:
                errs = "; ".join(str(e) for e in page_errors[:3])
                report(1, "Landing page loads", False,
                       f"HTTP {status_code}, JS errors: {errs or 'none'}")
        except Exception as e:
            report(1, "Landing page loads", False, str(e))

        await page.screenshot(path=f"{SCREENSHOT_DIR}/01_landing.png", full_page=False)

        # ── TEST 2: Floating pill nav ──────────────────────────────────────
        try:
            nav = page.locator("nav").first
            await nav.wait_for(state="visible", timeout=5000)
            nav_text = await nav.inner_text()
            expected = ["LateNightStack", "Products", "Pricing", "Telegram", "Get Started"]
            found_all = all(e in nav_text for e in expected)
            # Check for pill/floating style
            nav_class = await nav.get_attribute("class") or ""
            nav_style = await nav.evaluate("el => window.getComputedStyle(el).position")
            report(2, "Floating pill nav", found_all,
                   f"Nav text contains all labels={found_all}; position={nav_style}; classes='{nav_class[:80]}'")
        except Exception as e:
            report(2, "Floating pill nav", False, str(e))

        # ── TEST 3: Particle animation ─────────────────────────────────────
        try:
            # Look for canvas or particle container
            canvas = page.locator("canvas").first
            canvas_count = await page.locator("canvas").count()
            particle_div = await page.locator("[id*='particle'], [class*='particle'], [id*='tsparticles'], #particles-js, #particles").count()
            found = canvas_count > 0 or particle_div > 0
            report(3, "Particle animation", found,
                   f"canvas elements={canvas_count}, particle containers={particle_div}")
        except Exception as e:
            report(3, "Particle animation", False, str(e))

        # ── TEST 4: Hero section headline & glow orb ──────────────────────
        try:
            hero_text = await page.locator("body").inner_text()
            headline_present = "Turn AI Into Passive Income" in hero_text
            # Look for glow orb element
            orb_count = await page.locator("[class*='orb'], [class*='glow'], [class*='blob']").count()
            report(4, "Hero section", headline_present,
                   f"Headline found={headline_present}; glow/orb elements={orb_count}")
        except Exception as e:
            report(4, "Hero section", False, str(e))

        # ── TEST 5: Register modal ─────────────────────────────────────────
        try:
            # Find and click "Get Started"
            get_started = page.locator("a:has-text('Get Started'), button:has-text('Get Started')").first
            await get_started.scroll_into_view_if_needed()
            await get_started.click()
            await page.wait_for_timeout(1000)

            modal = page.locator("[class*='modal'], [role='dialog'], #auth-modal, .modal").first
            modal_visible = await modal.is_visible() if await page.locator("[class*='modal'], [role='dialog'], #auth-modal, .modal").count() > 0 else False

            modal_text = await modal.inner_text() if modal_visible else ""
            has_login_tab = "Login" in modal_text or "Sign In" in modal_text
            has_signup_tab = "Sign Up" in modal_text or "Register" in modal_text or "Create" in modal_text

            report(5, "Register modal", modal_visible and (has_login_tab or has_signup_tab),
                   f"Modal visible={modal_visible}, Login tab={has_login_tab}, SignUp tab={has_signup_tab}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/05_modal.png")
        except Exception as e:
            report(5, "Register modal", False, str(e))
            await page.screenshot(path=f"{SCREENSHOT_DIR}/05_modal_error.png")

        # ── TEST 6: Register a new user ────────────────────────────────────
        try:
            # Make sure we're on Sign Up tab
            signup_tab = page.locator("button:has-text('Sign Up'), [data-tab='signup'], .tab:has-text('Sign Up')").first
            if await signup_tab.count() > 0 and await signup_tab.is_visible():
                await signup_tab.click()
                await page.wait_for_timeout(500)

            # Fill in registration form
            name_field = page.locator("input[name='name'], input[placeholder*='name' i], input[placeholder*='Name']").first
            email_field = page.locator("input[type='email'], input[name='email']").first
            pass_field = page.locator("input[type='password']").first

            if await name_field.count() > 0:
                await name_field.fill("Test User")
            await email_field.fill("test123@gmail.com")
            await pass_field.fill("TestPass123")

            await page.screenshot(path=f"{SCREENSHOT_DIR}/06_before_register.png")

            # Click create account button
            create_btn = page.locator("button:has-text('Create Free Account'), button:has-text('Sign Up'), button:has-text('Register'), button[type='submit']").first
            await create_btn.click()
            await page.wait_for_timeout(2000)

            # Check for success/error
            page_text = await page.locator("body").inner_text()
            success_indicators = ["Welcome", "Dashboard", "Success", "Account created", "Logged in", "welcome back"]
            error_indicators = ["Error", "error", "failed", "already exists", "invalid"]

            success = any(s.lower() in page_text.lower() for s in success_indicators)
            error_msg = next((e for e in error_indicators if e.lower() in page_text.lower()), None)

            await page.screenshot(path=f"{SCREENSHOT_DIR}/06_after_register.png")
            report(6, "Register new user", success,
                   f"Success indicators found={success}; error found='{error_msg or 'none'}'")
        except Exception as e:
            report(6, "Register new user", False, str(e))
            await page.screenshot(path=f"{SCREENSHOT_DIR}/06_error.png")

        # ── TEST 7: Login ──────────────────────────────────────────────────
        try:
            # Re-open modal if closed, or find login tab
            modal_open = await page.locator("[class*='modal'], [role='dialog'], #auth-modal").count() > 0
            if not modal_open:
                btn = page.locator("a:has-text('Get Started'), button:has-text('Get Started'), a:has-text('Login'), button:has-text('Login')").first
                await btn.click()
                await page.wait_for_timeout(800)

            login_tab = page.locator("button:has-text('Login'), [data-tab='login'], .tab:has-text('Login'), a:has-text('Login')").first
            if await login_tab.count() > 0:
                await login_tab.click()
                await page.wait_for_timeout(500)

            email_field = page.locator("input[type='email'], input[name='email']").first
            pass_field = page.locator("input[type='password']").first
            await email_field.fill("test123@gmail.com")
            await pass_field.fill("TestPass123")

            await page.screenshot(path=f"{SCREENSHOT_DIR}/07_before_login.png")

            login_btn = page.locator("button:has-text('Login'), button:has-text('Sign In'), button:has-text('Log In'), button[type='submit']").first
            await login_btn.click()
            await page.wait_for_timeout(2000)

            page_text = await page.locator("body").inner_text()
            logged_in = any(w.lower() in page_text.lower() for w in ["Welcome", "Dashboard", "dashboard", "welcome back", "Logout", "Log out"])

            await page.screenshot(path=f"{SCREENSHOT_DIR}/07_after_login.png")
            report(7, "Login", logged_in, f"Login success indicators found={logged_in}")
        except Exception as e:
            report(7, "Login", False, str(e))

        # ── TEST 8: Dashboard appears ──────────────────────────────────────
        try:
            page_text = await page.locator("body").inner_text()
            has_welcome = any(w.lower() in page_text.lower() for w in ["welcome back", "Welcome back", "Welcome"])
            has_stats = any(w.lower() in page_text.lower() for w in ["bot", "stats", "active", "dashboard"])
            dashboard_el = await page.locator("[id*='dashboard'], [class*='dashboard'], #user-dashboard").count()

            report(8, "Dashboard appears after login", has_welcome or dashboard_el > 0,
                   f"'welcome back' found={has_welcome}, bot stats found={has_stats}, dashboard elements={dashboard_el}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/08_dashboard.png")
        except Exception as e:
            report(8, "Dashboard appears after login", False, str(e))

        # ── TEST 9: Scroll to Features ─────────────────────────────────────
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.3)")
            await page.wait_for_timeout(1000)

            page_text = await page.locator("body").inner_text()
            feature_cards = ["Intelligence", "Content", "Document", "Political", "Multilingual", "Real Estate"]
            found_cards = [f for f in feature_cards if f in page_text]

            report(9, "Scroll to Features", len(found_cards) >= 5,
                   f"Found {len(found_cards)}/6 feature cards: {found_cards}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/09_features.png")
        except Exception as e:
            report(9, "Scroll to Features", False, str(e))

        # ── TEST 10: Interstitial glow ─────────────────────────────────────
        try:
            page_text = await page.locator("body").inner_text()
            has_tagline = "Your bots work while you sleep" in page_text
            glow_el = await page.locator("[class*='interstitial'], [class*='glow-section'], section:has-text('bots work while you sleep')").count()

            report(10, "Interstitial glow", has_tagline,
                   f"Tagline present={has_tagline}, glow section elements={glow_el}")
        except Exception as e:
            report(10, "Interstitial glow", False, str(e))

        # ── TEST 11: Telegram section ──────────────────────────────────────
        try:
            page_text = await page.locator("body").inner_text()
            has_bot = "@EzAeyebot" in page_text or "EzAeyebot" in page_text
            telegram_el = await page.locator("[class*='telegram'], [class*='chat'], [id*='telegram']").count()
            has_demo = "demo" in page_text.lower() or has_bot

            report(11, "Telegram section", has_bot or telegram_el > 0,
                   f"@EzAeyebot found={has_bot}, telegram elements={telegram_el}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/11_telegram.png")
        except Exception as e:
            report(11, "Telegram section", False, str(e))

        # ── TEST 12: Pricing section ───────────────────────────────────────
        try:
            page_text = await page.locator("body").inner_text()
            plans = ["Free", "Starter", "Pro", "Business"]
            found_plans = [p for p in plans if p in page_text]

            # Check Pro highlighted (navy/blue glow)
            pro_card = page.locator("[class*='pricing'] [class*='pro'], [class*='plan-pro'], .pricing-card:has-text('Pro')").first
            pro_highlighted = await pro_card.count() > 0 if await page.locator("[class*='pricing']").count() > 0 else False

            report(12, "Pricing section", len(found_plans) == 4,
                   f"Found {len(found_plans)}/4 plans: {found_plans}; Pro highlighted={pro_highlighted}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/12_pricing.png")
        except Exception as e:
            report(12, "Pricing section", False, str(e))

        # ── TEST 13: PayPal buttons ────────────────────────────────────────
        try:
            page_text = await page.locator("body").inner_text()
            has_paypal_text = "PayPal" in page_text or "paypal" in page_text
            paypal_btns = await page.locator("[id*='paypal'], [class*='paypal'], iframe[src*='paypal']").count()
            has_separator = "or pay with" in page_text.lower() or "pay with" in page_text.lower()

            report(13, "PayPal buttons", has_paypal_text or paypal_btns > 0,
                   f"PayPal text={has_paypal_text}, PayPal elements={paypal_btns}, 'or pay with' separator={has_separator}")
        except Exception as e:
            report(13, "PayPal buttons", False, str(e))

        # ── TEST 14: CTA closer ────────────────────────────────────────────
        try:
            page_text = await page.locator("body").inner_text()
            has_cta = "Start building on LateNightStack" in page_text
            rings_el = await page.locator("[class*='ring'], [class*='concentric'], [class*='cta-rings']").count()

            report(14, "CTA closer", has_cta,
                   f"'Start building on LateNightStack' found={has_cta}, ring elements={rings_el}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/14_cta.png")
        except Exception as e:
            report(14, "CTA closer", False, str(e))

        # ── TEST 15: Footer ────────────────────────────────────────────────
        try:
            footer = page.locator("footer").first
            footer_visible = await footer.is_visible() if await page.locator("footer").count() > 0 else False
            footer_text = await footer.inner_text() if footer_visible else ""
            has_india = "India" in footer_text or "🇮🇳" in footer_text
            has_links = await page.locator("footer a").count() > 0

            report(15, "Footer", footer_visible and (has_india or has_links),
                   f"Footer visible={footer_visible}, 'Built in India'={has_india}, links count={await page.locator('footer a').count()}")
        except Exception as e:
            report(15, "Footer", False, str(e))

        # ── Final full-page screenshot ─────────────────────────────────────
        await page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(1500)
        await page.screenshot(path=f"{SCREENSHOT_DIR}/final_fullpage.png", full_page=True)
        print(f"\nFull-page screenshot saved: {SCREENSHOT_DIR}/final_fullpage.png")

        await browser.close()

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("FUNCTIONAL TEST SUMMARY — LateNightStack http://localhost:8000")
    print("="*70)
    passed = sum(1 for r in results if r[2] == "PASS")
    failed = sum(1 for r in results if r[2] == "FAIL")
    for num, name, status, detail in results:
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon} [{status}] #{num:02d} {name}")
        print(f"        {detail}")
    print(f"\n  Total: {passed} PASS / {failed} FAIL out of {len(results)} tests")
    print("="*70)


asyncio.run(run_tests())
