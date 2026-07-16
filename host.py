import asyncio
from contextlib import AsyncExitStack
from typing import Any

import httpx
from openai import OpenAI
from client import MCPClient
from dotenv import load_dotenv

load_dotenv()


class ChatHost:
    def __init__(self):
        # הגדרת שרת ה-MCP של מזג האוויר
        self.mcp_clients: list[MCPClient] = [MCPClient("./weather_Israel.py")]
        self.tool_clients: dict[str, tuple[MCPClient, str]] = {}
        self.clients_connected = False
        self.exit_stack = AsyncExitStack()
        
        # התאמה לסינון נטפרי באמצעות מעקף בדיקת ה-SSL עבור OpenAI API
        transport = httpx.HTTPTransport(verify=False)
        self.openai_client = OpenAI(http_client=httpx.Client(transport=transport))

    async def connect_mcp_clients(self):
        """Connect all configured MCP clients once."""
        if self.clients_connected:
            return

        for client in self.mcp_clients:
            if client.session is None:
                await client.connect_to_server()

        if not self.mcp_clients:
            raise RuntimeError("No MCP clients are connected")

        self.clients_connected = True

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Collect tools from all MCP clients and map them back to their owner."""
        await self.connect_mcp_clients()
        self.tool_clients = {}
        available_tools: list[dict[str, Any]] = []

        for client in self.mcp_clients:
            if client.session is None:
                print(f"Warning: MCP client {client.client_name} is not connected, skipping")
                continue

            try:
                response = await client.session.list_tools()
                for tool in response.tools:
                    exposed_name = f"{client.client_name}__{tool.name}"
                    if exposed_name in self.tool_clients:
                        raise RuntimeError(f"Duplicate tool name detected: {exposed_name}")

                    self.tool_clients[exposed_name] = (client, tool.name)
                    available_tools.append(
                        {
                            "name": exposed_name,
                            "description": f"[{client.client_name}] {tool.description}",
                            "input_schema": tool.inputSchema,
                        }
                    )
            except Exception as e:
                print(f"Warning: Failed to get tools from {client.client_name}: {str(e)}")
                continue

        if not available_tools:
            raise RuntimeError("No tools available from any MCP client")

        return available_tools

    async def process_query(self, query: str) -> str:
        """Process a query using OpenAI and available tools with strict loop protection."""
        messages = [
            {
                "role": "system",
                "content": """אתה עוזר חכם שמנווט באתר מזג האוויר בישראל באמצעות 3 כלים קבועים של ה-MCP.
עליך לבצע את שלושת השלבים הבאים בדיוק ובזה אחר זה, בלי לדלג על אף שלב ובלי לקרוא לאותו כלי כמה פעמים:

1. שלב ראשון - פתיחת האתר:
   קרא לכלי: `weather_Israel__open_weather_forecast_israel` (ללא ארגומנטים).
   המתן לקבלת תשובה שהאתר נפתח בהצלחה.

2. שלב שני - הקלדת שם העיר:
   קרא לכלי: `weather_Israel__enter_weather_forecast_city_israel` כאשר ב-`city_name` תעביר את שם העיר שהמשתמש ביקש (למשל: 'ירושלים').
   המתן לקבלת אישור שההקלדה בוצעה בהצלחה.

3. שלב שלישי - בחירה וניווט:
   קרא לכלי: `weather_Israel__select_weather_forecast_city_israel` (ללא ארגומנטים) כדי ללחוץ על מקש ה-Enter, לבחור את העיר ולעבור לעמוד התחזית שלה.

שים לב: אל תקרא לאותו כלי פעמיים באותו סבב! ברגע שקיבלת אישור שהשלב הצליח, עבור מיד לשלב הבא."""
            },
            {"role": "user", "content": query}
        ]
        
        available_tools = await self.get_available_tools()
        
        # המרה של פורמט הכלים לפורמט ש-OpenAI מצפה לקבל
        openai_tools = []
        for tool in available_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"]
                }
            })

        final_text = []
        # מעקב קשיח אחרי שמות הכלים שהורצו בסבב הנוכחי
        already_run_in_turn = set()

        while True:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=openai_tools if openai_tools else None,
                tool_choice="auto"
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            # הוספת תגובת העוזר להיסטוריית השיחה
            messages.append(response_message)

            if response_message.content:
                final_text.append(response_message.content)

            if not tool_calls:
                break

            # ניקוי מעקב הכלים לסבב הנוכחי
            already_run_in_turn.clear()

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                
                import json
                tool_args = json.loads(tool_call.function.arguments)

                if tool_name not in self.tool_clients:
                    raise RuntimeError(f"Unknown tool requested by model: {tool_name}")

                # הגנה מחמירה: אם המודל מנסה להפעיל את אותו שם כלי שוב באותו סבב - חוסמים אותו מיד
                if tool_name in already_run_in_turn:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": "הפעולה כבר בוצעה בהצלחה בסבב זה. נא לעבור לשלב הבא."
                    })
                    continue

                already_run_in_turn.add(tool_name)

                client, original_tool_name = self.tool_clients[tool_name]
                if client.session is None:
                    raise RuntimeError(f"MCP client {client.client_name} is not connected")

                # קריאה לכלי בפועל
                result = await client.session.call_tool(original_tool_name, tool_args)
                print(f"[Calling tool {tool_name} with args {tool_args}]")
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                
                # המרת תוצאת הכלי למחרוזת טקסט
                result_content = ""
                if isinstance(result.content, list):
                    result_content = "\n".join([item.text for item in result.content if hasattr(item, 'text')])
                else:
                    result_content = str(result.content)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": result_content
                })

        return "\n".join(final_text)
    
    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                
                response = await self.process_query(query)
                print("\n" + response)
                
            except Exception as e:
                print(f"\nchat_loop Error: {str(e)}")
                
    async def cleanup(self):
        """Clean up resources"""
        for client in reversed(self.mcp_clients):
            await client.cleanup()
        await self.exit_stack.aclose()
        
        
async def main():
    host = ChatHost()
    try:
        await host.chat_loop()
    finally:
        await host.cleanup()
        
if __name__ == "__main__":
    asyncio.run(main())