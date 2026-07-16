import time
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

mcp = FastMCP("Israel-Weather-Automation")

browser = None
page = None
pw = None

@mcp.tool()
async def init_browser():
    global browser, page, pw
    if page is None:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
# 3. הגדרת הכלים (Tools) עבור ה-AI - ללא העברת אובייקט ה-page מבחוץ
@mcp.tool()
async def open_forecast_page():
    await init_browser()
    await page.goto("https://www.weather2day.co.il/forecast")
    return "page opened"


@mcp.tool()
async def search_city(city_name: str):
    await init_browser()
    await page.locator("#city_search_forecast").fill(city_name)
    await page.keyboard.press("Enter")
    await page.wait_for_load_state("networkidle")
    return f"searched {city_name}"

@mcp.tool()
async def get_forecast_text() -> str:
    await init_browser()
    text = await page.locator("body").inner_text()
    return text[:1000]


# 4. הרצת שרת ה-MCP (השרת ימשיך לרוץ ויאזין לפקודות)
if __name__ == "__main__":
    mcp.run()