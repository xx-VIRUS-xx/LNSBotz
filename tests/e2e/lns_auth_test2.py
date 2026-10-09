import re, os
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = "/Users/xxvirusxx/PY/Bots/lns_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

results = []

def log(step, status, detail):
    msg = f"[{status}] Step {step}: {detail}"
    print(msg, flush=True)
    results.append(msg)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)

    # ── TEST 1: Sign-Up ──────────────────────────────────────────────────────
    ctx1 = browser.new_context(viewport={"width": 1280, "height": 900})
    p1 = ctx1.new_page()

    # Step 1 – Navigate
    try:
        p1.goto("https://latenightstack.latenightstack.com", wait_until="networkidle", timeout=30000)
        log(1, "PASS", "Loaded https://latenightstack.latenightstack.com")
    except Exception as e:
        log(1, "FAIL", str(e)); browser.close(); exit(1)

    # Step 2 – Click Get Started (pill nav)
    try:
        p1.locator("button.nav-cta-btn").first.click()
        p1.wait_for_timeout(1200)
        log(2, "PASS", "Clicked Get Started (pill nav)")
    except Exception as e:
        log(2, "FAIL", str(e))

    # Step 3 – Sign Up tab (already active, but click to confirm)
    try:
        # Tabs are button.tab — find the one with text Sign Up
        su_tab = p1.locator("button.tab:has-text('Sign Up')")
        su_tab.wait_for(timeout=5000)
        tab_class = su_tab.get_attribute("class") or ""
        if "active" not in tab_class:
            su_tab.click()
            p1.wait_for_timeout(600)
        log(3, "PASS", f"On Sign Up tab (class='{tab_class}')")
    except Exception as e:
        log(3, "FAIL", str(e))

    # Step 4 – Fill Sign Up form using exact IDs
    try:
        p1.locator("#r-name").wait_for(timeout=6000)
        p1.locator("#r-name").fill("Prabhat Test")
        p1.locator("#r-email").fill("prabhat.test2@latenightstack.ai")
        p1.locator("#r-pass").fill("LateNightStack2025!")
        log(4, "PASS", "Filled Name='Prabhat Test', email='prabhat.test2@latenightstack.ai', password='LateNightStack2025!'")
    except Exception as e:
        log(4, "FAIL", str(e))
        p1.screenshot(path=f"{SCREENSHOT_DIR}/step4_fail.png", full_page=True)

    # Step 5 – Click Create Free Account
    try:
        # There are two .submit buttons; Sign Up form's is "Create Free Account"
        p1.locator("button.submit:has-text('Create Free Account')").click()
        log(5, "PASS", "Clicked 'Create Free Account'")
    except Exception as e:
        log(5, "FAIL", str(e))
        p1.screenshot(path=f"{SCREENSHOT_DIR}/step5_fail.png", full_page=True)

    # Step 6 – Success message or dashboard
    p1.wait_for_timeout(4000)
    url1 = p1.url
    body1 = p1.inner_text("body")
    has_success = bool(re.search(r"success|verify|check.*email|account created|dashboard|welcome|sent", body1, re.I))
    on_dash1 = bool(re.search(r"dashboard", url1, re.I)) or bool(re.search(r"dashboard", body1, re.I))
    # capture snippet
    snippet1 = re.sub(r'\s+', ' ', body1[:300]).strip()
    log(6, "PASS" if (has_success or on_dash1) else "FAIL",
        f"URL={url1} | success={has_success} | dashboard={on_dash1} | preview='{snippet1[:120]}'")
    p1.screenshot(path=f"{SCREENSHOT_DIR}/signup_result.png", full_page=True)
    log("6-ss", "PASS", "Screenshot saved -> signup_result.png")
    ctx1.close()

    # ── TEST 2: Login ────────────────────────────────────────────────────────
    ctx2 = browser.new_context(viewport={"width": 1280, "height": 900})
    p2 = ctx2.new_page()

    try:
        p2.goto("https://latenightstack.latenightstack.com", wait_until="networkidle", timeout=30000)
        log("8a", "PASS", "Re-loaded site for login test")
    except Exception as e:
        log("8a", "FAIL", str(e))

    # Click Get Started
    try:
        p2.locator("button.nav-cta-btn").first.click()
        p2.wait_for_timeout(1200)
        log("8b", "PASS", "Clicked Get Started")
    except Exception as e:
        log("8b", "FAIL", str(e))

    # Click Login tab
    try:
        login_tab = p2.locator("button.tab:has-text('Login')")
        login_tab.wait_for(timeout=6000)
        login_tab.click()
        p2.wait_for_timeout(600)
        log("8c", "PASS", "Clicked Login tab")
    except Exception as e:
        log("8c", "FAIL", str(e))

    # Fill login form with exact IDs
    try:
        p2.locator("#l-email").wait_for(timeout=6000)
        p2.locator("#l-email").fill("prabhat@latenightstack.ai")
        p2.locator("#l-pass").fill("LateNightStack2025!")
        log("8d", "PASS", "Filled login email + password")
    except Exception as e:
        log("8d", "FAIL", str(e))
        p2.screenshot(path=f"{SCREENSHOT_DIR}/login_fill_fail.png", full_page=True)

    # Click Sign In
    try:
        p2.locator("button.submit:has-text('Sign In')").click()
        log("8e", "PASS", "Clicked 'Sign In'")
    except Exception as e:
        log("8e", "FAIL", str(e))
        p2.screenshot(path=f"{SCREENSHOT_DIR}/signin_btn_fail.png", full_page=True)

    # Step 9 – Dashboard
    p2.wait_for_timeout(5000)
    url2 = p2.url
    body2 = p2.inner_text("body")
    on_dash2 = bool(re.search(r"dashboard", url2, re.I)) or bool(re.search(r"dashboard", body2, re.I))
    welcome = (re.search(r"welcome[\s\S]{0,80}", body2, re.I) or [""])[0][:80].strip()
    plan = (re.search(r"(free|pro|starter|enterprise|plan)\s*[\w\s]{0,30}", body2, re.I) or [""])[0][:40].strip()
    bots = (re.search(r"\d+\s*(bot|agent)", body2, re.I) or [""])[0][:30].strip()
    snippet2 = re.sub(r'\s+', ' ', body2[:400]).strip()
    log(9, "PASS" if on_dash2 else "FAIL",
        f"URL={url2} | dashboard={on_dash2} | welcome='{welcome}' | plan='{plan}' | bots='{bots}'")
    log("9-detail", "INFO", f"Body preview: '{snippet2[:150]}'")
    p2.screenshot(path=f"{SCREENSHOT_DIR}/login_dashboard.png", full_page=True)
    log("9-ss", "PASS", "Screenshot saved -> login_dashboard.png")

    ctx2.close()
    browser.close()

print("\n=== SUMMARY ===")
for r in results:
    print(r)
