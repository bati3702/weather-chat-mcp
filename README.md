# 🌦️ Weather Israel MCP Server (Playwright)

> **The MCP that puts the LLM's hand on the mouse.**  
> Weather forecasts Made in Israel — not through a boring API, but the Israeli way: open a browser, poke your nose into the site, type, click... and get a forecast.

---

## 🎯 What is this project?

In the classic Weather MCP example, the LLM pulls weather data through a US API. Nice, but... who really cares about a forecast somewhere in the USA when you need the current temperature in Tel Aviv or Jerusalem?

This project builds an Israeli MCP Server that gives the LLM a completely human ability: to control a real browser. Instead of calling an API, the Agent:
1. Opens a real Chromium browser (in headless=False mode, so you can watch it live!).
2. Types a city name into the search field of weather2day.co.il.
3. Picks the city from the autocomplete dropdown dynamically.
4. Scrapes the page content, cleans it, and feeds it back to the LLM so it can answer on its own (Retrieval-Augmented Generation / RAG).

The big idea: Everything a human user does with two hands — the LLM learns to do with four Tools.

---

## 🧠 What you'll learn

* Build your own MCP Server for any purpose or targeted website.
* Expose Python functions as Tools for an LLM using the FastMCP decorator.
* Use Playwright to give an LLM physical control over a browser (mouse & keyboard simulation).
* Build RAG (Retrieval-Augmented Generation): Stream live, freshly-scraped page content directly into the model's context.
* Sync & Stability: Handle dynamic web element loading and prevent flakiness in browser automation.

---

## 📂 Project Structure

project-template/
├── weather_Israel.py   # MCP Server — Israel forecast via Playwright
├── host.py             # Terminal chat — connects the LLM to the MCP server
├── client.py           # Generic MCP Client (stdio communication)
├── pyproject.toml      # Project dependencies and metadata (uv)
└── .env                # Environment variables (OpenAI API key)

---

## 🛠️ Technologies Used

* Python 3.13+
* FastMCP (MCP SDK) - Anthropic's official framework for building Model Context Protocol servers easily.
* Playwright (Python Async API) - Advanced browser automation and control library.
* OpenAI API - The brain of the Agent (powered by gpt-4o-mini), deciding which tools to call and interpreting the results.

---

## 🧩 The Four Tools of the Israeli MCP

The manual steps a human performs on the website are broken down into 4 modular tools that the LLM calls sequentially:

| Tool | What it does | Human equivalent |
| :--- | :--- | :--- |
| open_weather_forecast_israel | Launches Chromium in non-headless mode and navigates to the forecast site. | Open a browser and go to the site. |
| enter_weather_forecast_city_israel(city) | Finds the search field, clears it, and types the city name char-by-char to trigger autocomplete. | Click the search bar and type the city name. |
| select_weather_forecast_city_israel | Detects the dropdown list, clicks the first auto-complete suggestion, and waits for the city page to load. | Click on the correct city from the suggestions. |
| get_forecast_content_israel | Scrapes the loaded page, cleans up redundant spaces and empty lines, and feeds it back to the LLM. | Read the forecast details on the screen. |

> Why not just search Google?  
> Running a Google search through automated browsers quickly triggers CAPTCHA challenges. By guiding the Agent through a direct, targeted flow on a specific website, we bypass bot detection completely and guarantee a seamless run.

---

## 🛡️ Loop Protection (מנגנון מניעת לולאות)

During development, we identified that LLMs can sometimes get stuck in an infinite loop, calling the same tool repeatedly (such as trying to open the browser over and over). 

To prevent this, we implemented a strict Loop Protection Mechanism inside host.py:
* The host keeps track of all executed tools within the current turn.
* If the LLM tries to invoke the same tool more than once per turn, the call is blocked and a system message is returned: "This action has already been completed in this turn. Please proceed to the next step."
* This forces the LLM to progress linearly: Open ➔ Type ➔ Select ➔ Scrape.

---

## 🚀 Setup & Run (שלב אחר שלב)

This project is managed using uv for ultra-fast dependency management.

1. Install dependencies and set up the environment:
   Command: uv sync

2. Install the Chromium browser for Playwright:
   Command: uv run playwright install chromium

3. Configure your API key:
   Create a .env file in the project root and add your OpenAI API key:
   OPENAI_API_KEY=your_actual_api_key_here
   (The .env file is already listed in .gitignore to ensure your secret key is never pushed to public repositories).

4. Start the Chat Agent:
   Command: uv run host.py
   
   Type your query in the terminal, press Enter, and watch the browser open and perform the actions on its own! To exit, simply type "quit".

---

## 💬 Example Questions to Try

The Agent will analyze your request and trigger the correct sequence of tools automatically. Try asking:
* "מה מזג האוויר בירושלים היום?" (What's the weather in Jerusalem today?)
* "Check the temperature in Tel Aviv for the upcoming days"
* "האם צפוי לרדת גשם בחיפה מחר? מה אחוזי הלחות?"

---

## 💭 A Closing Thought

Playwright was born long before the GenAI era — originally designed as a testing automation tool for developers. But with the rise of AI Agents, it has taken center stage. Suddenly, giving an LLM "hands and a mouse" to interact with the real web has become the ultimate way to bridge the gap between static knowledge and real-world actions.
