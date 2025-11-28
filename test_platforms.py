#!/usr/bin/env python3
"""Test script to check platform search with stealth mode"""
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

stealth = Stealth()

async def test_platform(name, url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='Europe/Berlin'
        )
        page = await context.new_page()
        
        # Apply stealth mode
        await stealth.apply_stealth_async(page)
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for Cloudflare
            await asyncio.sleep(3)
            
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            title = soup.title.string if soup.title else 'No title'
            print(f'\n{name}: {title[:50]}')
            print(f'  HTML length: {len(html)}')
            
            # Check for Cloudflare block
            if 'Cloudflare' in html or 'cf-browser-verification' in html:
                print('  ⚠️  Cloudflare challenge detected!')
            
            # Check for articles
            articles = soup.select('article')
            print(f'  Articles: {len(articles)}')
            
            # Show first few article titles
            for a in articles[:3]:
                title_el = a.select_one('h2, h3, h4, a')
                if title_el:
                    print(f'    - {title_el.get_text(strip=True)[:50]}')
                    
        except Exception as e:
            print(f'{name}: ERROR - {e}')
        finally:
            await browser.close()


async def main():
    platforms = [
        ('Times of Israel', 'https://www.timesofisrael.com/?s=technology'),
        ('Heise', 'https://www.heise.de/suche/?q=technology&sort=date'),
    ]
    for name, url in platforms:
        await test_platform(name, url)


if __name__ == '__main__':
    asyncio.run(main())
