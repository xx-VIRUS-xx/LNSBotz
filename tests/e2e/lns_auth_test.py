import re, sys, os
from playwright.sync_api import sync_playwright, TimeoutError as PTE

SCREENSHOT_DIR = "/Users/xxvirusxx/PY/Bots/lns_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

results = []

def log(step, status, detail):
    msg = f"[{status}] Step {step}: {detail}"
    print(msg, flush=True)
    results.append(msg)

def try_click(page, selectors, label, timeout=8000):
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=timeout)
            el.click()
            return True
        except Exception:
            pass
    log("?", "FAIL", f"Could not find/click: {label}")
    return False

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
        log(1, "FAIL", str(e))
        p1.screenshot(path=f"{SCREENSHOT_DIR}/step1_fail.png", full_page=True)
        browser.close(); sys.exit(1)

    # Step 2 – Click Get Started
    ok = try_click(p1, ["text=Get Started", "button:has-text('Get Started')", "[class*='pill'] >> text=Get Started"], "Get Started")
    log(2, "PASS" if ok else "FAIL", "Clicked Get Started" if ok else "Get Started button not found")
    p1.wait_for_timeout(1200)

    # Step 3 – Switch to Sign Up tab
    ok = try_click(p1,
        ["[role='tab']:has-text('Sign Up')", "button:has-text('Sign Up')",
         "text=Sign Up", "[data-state] >> text=Sign Up"],
        "Sign Up tab")
    log(3, "PASS" if ok else "FAIL", "Switched to Sign Up tab" if ok else "Already on Sign Up / not found")
    p1.wait_for_timeout(600)

    # Step 4 – Fill form
    try:
        name_sel = "input[name='name'], input[placeholder*='Name' i], input[placeholder*='name' i]"
        p1.locator(name_sel).first.wait_for(timeout=8000)
        p1.locator(name_sel).first.fill("Prabhat Test")

        email_sel = "input[type='email'], input[name='email'], input[placeholder*='email' i]"
        p1.locator(email_sel).first.fill("prabhat.test2@latenightstack.ai")

        pw_sel = "input[type='password']"
        p1.locator(pw_sel).first.fill("LateNightStack2025!")
        log(4, "PASS", "Filled Name, Email, Password")
    except Exception as e:
        log(4, "FAIL", str(e))
        p1.screenshot(path=f"{SCREENSHOT_DIR}/step4_fail.png", full_page=True)

    # Step 5 – Click Create Free Account
    ok = try_click(p1,
        ["button:has-text('Create Free Account')", "text=Create Free Account"],
        "Create Free Account")
    log(5, "PASS" if ok else "FAIL", "Clicked Create Free Account" if ok else "Button not found")

    # Step 6 – Success / Dashboard check
    p1.wait_for_timeout(4000)
    url_after = p1.url
    body = p1.inner_text("body")
    has_success = bool(re.search(r"success|verify|check.*email|account created|dashboard|welcome", body, re.I))
    on_dashboard = bool(re.search(r"dashboard", url_after, re.I)) or bool(re.search(r"dashboard", body, re.I))
    log(6, "PASS" if (has_success or on_dashboard) else "FAIL",
        f"URL={url_after} | success_msg={has_success} | dashboard={on_dashboard}")
    p1.screenshot(path=f"{SCREENSHOT_DIR}/signup_result.png", full_page=True)
    log("6-ss", "PASS", "Screenshot -> signup_result.png")
    ctx1.close()

    # ── TEST 2: Login ────────────────────────────────────────────────────────
    ctx2 = browser.new_context(viewport={"width": 1280, "height": 900})
    p2 = ctx2.new_page()

    # Re-navigate
    try:
        p2.goto("https://latenightstack.latenightstack.com", wait_until="networkidle", timeout=30000)
        log("8a", "PASS", "Re-loaded site for login test")
    except Exception as e:
        log("8a", "FAIL", str(e))

    # Click Get Started
    ok = try_click(p2, ["text=Get Started", "button:has-text('Get Started')"], "Get Started")
    log("8b", "PASS" if ok else "FAIL", "Clicked Get Started")
    p2.wait_for_timeout(1000)

    # Click Login tab
    ok = try_click(p2,
        ["[role='tab']:has-text('Login')", "[role='tab']:has-text('Sign In')",
         "button:has-text('Login')", "text=Login"],
        "Login tab")
    log("8c", "PASS" if ok else "FAIL", "Clicked Login tab" if ok else "Login tab not found")
    p2.wait_for_timeout(600)

    # Fill login
    try:
        email_sel = "input[type='email'], input[name='email'], input[placeholder*='email' i]"
        p2.locator(email_sel).first.wait_for(timeout=8000)
        p2.locator(email_sel).first.fill("prabhat@latenightstack.ai")
        p2.locator("input[type='password']").first.fill("LateNightStack2025!")
        log("8d", "PASS", "Filled login email + password")
    except Exception as e:
        log("8d", "FAIL", str(e))
        p2.screenshot(path=f"{SCREENSHOT_DIR}/login_fill_fail.png", full_page=True)

    # Click Sign In
    ok = try_click(p2,
        ["button:has-text('Sign In')", "button:has-text('Log In')",
         "button:has-text('Login')", "input[type='submit']"],
        "Sign In button")
    log("8e", "PASS" if ok else "FAIL", "Clicked Sign In" if ok else "Sign In button not found")

    # Step 9 – Dashboard screenshot
    p2.wait_for_timeout(5000)
    url2 = p2.url
    body2 = p2.inner_text("body")
    on_dash2 = bool(re.search(r"dashboard", url2, re.I)) or bool(re.search(r"dashboard", body2, re.I))
    welcome = (re.search(r"welcome[\s\S]{0,80}", body2, re.I) or [""])[0][:80].strip()
    plan = (re.search(r"(free|pro|starter|enterprise|plan)\s*[\w\s]{0,30}", body2, re.I) or [""])[0][:40].strip()
    bots = (re.search(r"\d+\s*(bot|agent)", body2, re.I) or [""])[0][:30].strip()
    log(9, "PASS" if on_dash2 else "FAIL",
        f"URL={url2} | welcome='{welcome}' | plan='{plan}' | bots='{bots}'")
    p2.screenshot(path=f"{SCREENSHOT_DIR}/login_dashboard.png", full_page=True)
    log("9-ss", "PASS", "Screenshot -> login_dashboard.png")

    ctx2.close()
    browser.close()

print("\n=== SUMMARY ===")
for r in results:
    print(r)
