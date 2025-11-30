#!/usr/bin/env python3
"""
Script for å hente brøytedata fra Plowman livekart.

Bruker Selenium for å hente data siden API-et krever JavaScript-rendering.
"""

import json
import re
from datetime import datetime
from typing import Optional

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def fetch_with_playwright() -> Optional[dict]:
    """Henter brøytedata med Playwright."""
    if not PLAYWRIGHT_AVAILABLE:
        print("Playwright ikke installert. Installer med: pip install playwright && playwright install")
        return None
    
    url = "https://plowman-new.xn--snbryting-m8ac.net/share/Y3VzdG9tZXItMTM="
    
    with sync_playwright() as p:
        # Bruk Firefox for å unngå bot-deteksjon
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        # Lytt på ALLE nettverksforespørsler
        all_responses = []
        
        def handle_response(response):
            url_str = response.url
            try:
                # Bare logg URL-er for debugging
                if 'plowman' in url_str or '_next' in url_str:
                    print(f"  Response: {response.status} {url_str[:100]}")
                # Fang alle JSON-responser
                content_type = response.headers.get('content-type', '')
                if 'json' in content_type:
                    try:
                        data = response.json()
                        all_responses.append({
                            'url': url_str,
                            'status': response.status,
                            'data': data
                        })
                        print(f"  JSON fanget: {url_str[:80]}...")
                    except:
                        pass
            except:
                pass
        
        page.on('response', handle_response)
        
        print(f"Åpner {url}...")
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        
        # Vent litt for at alt skal lastes
        print("Venter på lasting...")
        page.wait_for_timeout(8000)
        
        # Hent __NEXT_DATA__ direkte fra siden
        next_data = None
        try:
            next_data_content = page.evaluate('''() => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? el.textContent : null;
            }''')
            if next_data_content:
                next_data = json.loads(next_data_content)
                print("Fant __NEXT_DATA__ i siden")
        except Exception as e:
            print(f"Kunne ikke hente __NEXT_DATA__: {e}")
        
        # Lagre hele HTML-en for analyse
        page_content = page.content()
        with open('plowman_page.html', 'w') as f:
            f.write(page_content)
        print(f"HTML lagret til plowman_page.html ({len(page_content)} bytes)")
        
        # Ta et skjermbilde
        page.screenshot(path='plowman_screenshot.png')
        print("Skjermbilde lagret til plowman_screenshot.png")
        
        browser.close()
        
        return {
            'api_calls': all_responses,
            'next_data': next_data,
            'html_length': len(page_content),
            'timestamp': datetime.now().isoformat()
        }


def fetch_with_selenium() -> Optional[dict]:
    """Henter brøytedata med Selenium."""
    if not SELENIUM_AVAILABLE:
        print("Selenium ikke installert. Installer med: pip install selenium")
        return None
    
    url = "https://plowman-new.xn--snbryting-m8ac.net/share/Y3VzdG9tZXItMTM="
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        print(f"Åpner {url}...")
        driver.get(url)
        
        # Vent på at siden skal laste
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Hent __NEXT_DATA__ som inneholder preloaded data
        try:
            next_data_element = driver.find_element(By.ID, "__NEXT_DATA__")
            next_data = json.loads(next_data_element.get_attribute('innerHTML'))
            return next_data
        except:
            pass
        
        # Prøv å hente fra window.__NUXT__ eller lignende
        scripts = driver.find_elements(By.TAG_NAME, "script")
        for script in scripts:
            content = script.get_attribute('innerHTML')
            if content and ('sectors' in content.lower() or 'units' in content.lower()):
                print(f"Fant script med data: {content[:200]}...")
        
        # Hent hele HTML for analyse
        html = driver.page_source
        return {'html': html[:5000], 'timestamp': datetime.now().isoformat()}
        
    finally:
        driver.quit()


def parse_plowing_times(data: dict) -> list:
    """Parser brøytetider fra API-respons."""
    plowing_times = []
    
    if 'api_calls' in data:
        for call in data['api_calls']:
            url = call.get('url', '')
            response_data = call.get('data', {})
            
            print(f"\nAPI-kall: {url}")
            print(f"Data: {json.dumps(response_data, indent=2, default=str)[:1000]}")
            
            # Se etter aktivitetsdata
            if 'activity' in url.lower() or 'report' in url.lower():
                if isinstance(response_data, list):
                    for item in response_data:
                        if 'timestamp' in item or 'lastActivity' in item:
                            plowing_times.append(item)
    
    return plowing_times


def main():
    print("=" * 60)
    print("Henter brøytedata fra Plowman livekart")
    print("=" * 60)
    print()
    
    data = None
    
    # Prøv Playwright først (vanligvis mer pålitelig)
    if PLAYWRIGHT_AVAILABLE:
        print("Bruker Playwright...")
        data = fetch_with_playwright()
    elif SELENIUM_AVAILABLE:
        print("Bruker Selenium...")
        data = fetch_with_selenium()
    else:
        print("FEIL: Verken Playwright eller Selenium er installert.")
        print()
        print("Installer en av dem:")
        print("  pip install playwright && playwright install chromium")
        print("  eller")
        print("  pip install selenium")
        return
    
    if data:
        print("\n" + "=" * 60)
        print("RESULTATER")
        print("=" * 60)
        
        if 'api_calls' in data:
            print(f"\nFant {len(data['api_calls'])} API-kall:")
            for call in data['api_calls']:
                print(f"\n  URL: {call['url']}")
                print(f"  Status: {call.get('status', 'N/A')}")
                data_str = json.dumps(call['data'], indent=4, default=str)
                print(f"  Data: {data_str[:1000]}")
        
        if data.get('next_data'):
            print("\n" + "-" * 40)
            print("__NEXT_DATA__ innhold:")
            next_str = json.dumps(data['next_data'], indent=2, default=str)
            print(next_str[:3000])
        
        # Lagre til fil for analyse
        output_file = "plowing_data.json"
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"\nData lagret til {output_file}")
    else:
        print("Kunne ikke hente data.")


if __name__ == "__main__":
    main()
