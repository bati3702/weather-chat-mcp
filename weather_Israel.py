from mcp.server.fastmcp import FastMCP
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

mcp = FastMCP("weather-Israel")

FORECAST_URL = "https://www.weather2day.co.il/forecast"

_playwright = None
_browser    = None
_page       = None
_selected_city = None  # שם העיר האחרונה שנבחרה, לצורך אימות שהדף הנכון נטען

# טקסט שמופיע רק בדף התחזית הספציפי של עיר (ולא בדף הכללי) –
# משמש לוודא שהניווט לעיר הסתיים לפני שליפת התוכן.
_CITY_PAGE_MARKER = "עדכון אחרון"


async def _wait_for_city_page(page, timeout_ms: int = 15_000) -> bool:
    """
    ממתין עד שדף התחזית של עיר ספציפית נטען במלואו, ע"י בדיקה חוזרת
    של טקסט הדף (אותו טקסט שנשלף בהמשך) עד שה-marker מופיע בו.
    זו שיטה יציבה יותר מ-get_by_text כי היא בודקת בדיוק את מה שנשלף.
    מחזיר True אם הדף נטען, ו-False אם עבר ה-timeout.
    """
    elapsed = 0
    step = 500
    while elapsed < timeout_ms:
        try:
            text = await page.locator("body").inner_text()
            if _CITY_PAGE_MARKER in text:
                return True
        except Exception:
            pass
        await page.wait_for_timeout(step)
        elapsed += step
    return False


@mcp.tool()
async def open_weather_forecast_israel() -> str:
    """
    פותח דפדפן Chromium ומנווט לאתר מזג האויר הישראלי.
    יש לקרוא לפונקציה זו ראשונה לפני כל פעולה אחרת.
    """
    global _playwright, _browser, _page

    if _browser is not None:
        await _browser.close()
        await _playwright.stop()

    _playwright = await async_playwright().start()
    # slow_mo גבוה + חלון ממוקסם כדי שנוכל לראות בבירור את האוטומציה קורית
    _browser = await _playwright.chromium.launch(
        headless=False,
        slow_mo=400,
        args=["--start-maximized"],
    )
    # no_viewport=None כדי שהדף יתפוס את כל חלון הדפדפן הממוקסם
    context = await _browser.new_context(no_viewport=True)
    _page = await context.new_page()

    # מביא את חלון הדפדפן לקדמת המסך (מעל הטרמינל)
    await _page.bring_to_front()

    # networkidle – מחכה שגם ה-JavaScript של הדף יסיים לרוץ
    await _page.goto(FORECAST_URL, wait_until="networkidle")

    return f"✅ הדפדפן נפתח בהצלחה ועבר לכתובת: {FORECAST_URL}"


@mcp.tool()
async def enter_weather_forecast_city_israel(city: str) -> str:
    """
    מזין שם עיר בשדה החיפוש שבדף מזג האויר.
    יש לקרוא לפונקציה open_weather_forecast_israel לפני שימוש בפונקציה זו.

    Args:
        city: שם העיר לחיפוש (לדוגמה: 'תל אביב', 'ירושלים')
    """
    global _page

    if _page is None:
        return "❌ שגיאה: הדפדפן לא פתוח. קרא תחילה ל-open_weather_forecast_israel."

    try:
        # מציאת שדה הקלט לפי ה-ID האמיתי מה-DevTools
        search_input = _page.locator("#city_search_forecast")
        await search_input.wait_for(state="visible", timeout=10_000)

        await search_input.click()
        await search_input.fill("")

        # הקלדה תו-תו כדי להפעיל את ה-autocomplete
        await search_input.type(city, delay=100)

        # המתנה לטעינת רשימת ההצעות
        await _page.wait_for_timeout(1_500)

        return f"✅ העיר '{city}' הוזנה בהצלחה בשדה החיפוש."

    except PlaywrightTimeout:
        return "❌ שגיאת טיימאוט: שדה החיפוש לא נמצא תוך 10 שניות."
    except Exception as e:
        return f"❌ שגיאה בעת הזנת העיר: {e}"


@mcp.tool()
async def select_weather_forecast_city_israel() -> str:
    """
    בוחרת את הפריט הראשון ברשימת הערים שהופיעה לאחר ההקלדה.
    יש לקרוא תחילה ל-enter_weather_forecast_city_israel.
    """
    global _page, _selected_city

    if _page is None:
        return "❌ שגיאה: הדפדפן לא פתוח."

    try:
        # מה-DevTools רואים: הפריטים הם <div> ישירים בתוך autocomplete-list
        # כל div מכיל: טקסט + <input type="hidden" value="שם העיר">
        first_suggestion = _page.locator(
            "#city_search_forecastautocomplete-list > div"
        ).first

        # אם לא הופיעה אף הצעה – כנראה שם העיר לא נמצא באתר
        try:
            await first_suggestion.wait_for(state="visible", timeout=10_000)
        except PlaywrightTimeout:
            return ("❌ לא נמצאו הצעות ערים. ייתכן ששם העיר שגוי או לא קיים באתר. "
                    "נסה להזין שוב עיר בעזרת enter_weather_forecast_city_israel.")

        # שליפת שם העיר מה-input hidden שבתוך ה-div
        city_text = await first_suggestion.locator("input[type='hidden']").get_attribute("value")

        # לחיצה על הפריט הראשון
        await first_suggestion.click()

        # המתנה לטעינת דף התחזית
        await _page.wait_for_load_state("networkidle", timeout=15_000)

        # ⭐ תיקון flakiness: לוודא שהדף הספציפי של העיר באמת נטען
        # (ולא נשארנו בדף הכללי) לפני שממשיכים.
        loaded = await _wait_for_city_page(_page, timeout_ms=15_000)
        if not loaded:
            return ("❌ שגיאת טיימאוט: דף התחזית של העיר לא נטען במלואו תוך הזמן הקצוב. "
                    "נסה שוב.")

        _selected_city = city_text
        return f"✅ נבחרה העיר: '{city_text}'. דף התחזית נטען בהצלחה."

    except PlaywrightTimeout:
        return ("❌ שגיאת טיימאוט: דף התחזית של העיר לא נטען במלואו תוך הזמן הקצוב. "
                "נסה שוב.")
    except Exception as e:
        return f"❌ שגיאה בעת בחירת העיר: {e}"
    
@mcp.tool()
async def get_forecast_content_israel() -> str:
    """
    מחלצת את תוכן התחזית מהדף הטעון לאחר בחירת עיר.
    יש לקרוא לפונקציה זו רק לאחר בחירת העיר ב-select_weather_forecast_city_israel.
    """
    global _page

    if _page is None:
        return "❌ שגיאה: הדפדפן לא פתוח."

    try:
        # ⭐ תיקון flakiness: לוודא שדף התחזית של העיר באמת מוצג לפני השליפה,
        # כדי לא לשלוף בטעות את תוכן הדף הכללי. אם עדיין לא בחרו עיר – מדווחים.
        loaded = await _wait_for_city_page(_page, timeout_ms=15_000)
        if not loaded:
            return ("❌ דף התחזית של עיר ספציפית עדיין לא מוצג. "
                    "יש לבחור עיר תחילה ב-select_weather_forecast_city_israel.")

        # אנו נתמקד באזור התחזית העיקרי (לרוב יש אלמנט שמכיל את הטבלה או המידע)
        # נבצע ניקוי של תגיות HTML מיותרות ונשאיר רק טקסט נקי
        forecast_container = _page.locator("body") # ניתן לצמצם ל-selector ספציפי אם ידוע

        # המתנה קצרה לוודא שהתוכן התרנדר
        await _page.wait_for_timeout(1000)

        # שליפת הטקסט הנקי מכל הדף (או מאזור ספציפי)
        content = await forecast_container.inner_text()
        
        # ניקוי בסיסי: מחיקת שורות ריקות מרובות
        cleaned_content = "\n".join([line.strip() for line in content.splitlines() if line.strip()])
        
        return f"תוכן התחזית שנשלף:\n\n{cleaned_content[:4000]}" # הגבלה ל-4000 תווים כדי לא להעמיס על ה-Token window

    except Exception as e:
        return f"❌ שגיאה בחילוץ התוכן: {e}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()