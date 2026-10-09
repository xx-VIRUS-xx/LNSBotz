from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()

    page.goto("https://latenightstack.latenightstack.com", wait_until="networkidle", timeout=30000)
    print("=== INITIAL PAGE ===")
    print("URL:", page.url)

    # Click Get Started
    page.locator("text=Get Started").first.click()
    page.wait_for_timeout(1500)

    print("\n=== After Get Started ===")
    page.screenshot(path="/Users/xxvirusxx/PY/Bots/lns_screenshots/inspect1_after_getstartd.png", full_page=True)

    # Dump all input fields
    inputs = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('input')).map(el => ({
            id: el.id,
            name: el.name,
            type: el.type,
            placeholder: el.placeholder,
            visible: el.offsetParent !== null,
            class: el.className.substring(0, 60)
        }))
    }""")
    print("\nAll inputs:")
    for inp in inputs:
        print(inp)

    # Dump all tabs/buttons
    tabs = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('[role="tab"], button, .tab, [class*="tab"]')).slice(0, 30).map(el => ({
            tag: el.tagName,
            text: el.innerText.trim().substring(0, 40),
            role: el.getAttribute('role'),
            class: el.className.substring(0, 60),
            ariaSelected: el.getAttribute('aria-selected'),
            dataState: el.getAttribute('data-state')
        }))
    }""")
    print("\nTabs/Buttons:")
    for t in tabs:
        print(t)

    # Try clicking Sign Up tab
    print("\n=== Trying Sign Up tab click ===")
    su_tabs = page.evaluate("""() => {
        const tabs = document.querySelectorAll('[role="tab"]');
        return Array.from(tabs).map(t => ({text: t.innerText.trim(), selected: t.getAttribute('aria-selected'), state: t.getAttribute('data-state')}))
    }""")
    print("Tabs found:", su_tabs)

    try:
        su = page.locator("[role='tab']:has-text('Sign Up')").first
        su.wait_for(timeout=5000)
        su.click()
        page.wait_for_timeout(800)
        print("Clicked Sign Up tab")
    except Exception as e:
        print("Could not click Sign Up tab:", e)

    # Check inputs again after click
    inputs2 = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('input')).map(el => ({
            id: el.id,
            name: el.name,
            type: el.type,
            placeholder: el.placeholder,
            visible: el.offsetParent !== null,
            class: el.className.substring(0, 60)
        }))
    }""")
    print("\nInputs after Sign Up tab click:")
    for inp in inputs2:
        print(inp)

    page.screenshot(path="/Users/xxvirusxx/PY/Bots/lns_screenshots/inspect2_signup_tab.png", full_page=True)

    browser.close()
