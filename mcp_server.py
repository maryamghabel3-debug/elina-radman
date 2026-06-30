"""
MCP (Model Context Protocol) Server for ElinaOS
This exposes Elina's tools (Content Creation, Trend Hunting, Video Generation)
to any MCP-compatible AI Assistant (like Claude Desktop, Cursor, etc.)
"""

import os
import json
from mcp.server import Server, NotificationOptions
import mcp.types as types
from mcp.server.models import InitializationOptions

# Initialize the MCP Server
app = Server("ElinaOS")

# Define tools
@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools for ElinaOS."""
    return [
        types.Tool(
            name="generate_caption",
            description="Generate a new Instagram caption matching Elina's persona.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pillar": {"type": "string", "description": "e.g., 'petite_styling', 'psychology_of_style'"},
                },
                "required": ["pillar"]
            }
        ),
        types.Tool(
            name="get_current_trends",
            description="Fetch current fashion trends from Elina's TrendHunter agent.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        types.Tool(
            name="save_diary_entry",
            description="Save a new feeling/thought to Elina's emotional diary.",
            inputSchema={
                "type": "object",
                "properties": {
                    "feeling": {"type": "string", "description": "Elina's current emotional state."}
                },
                "required": ["feeling"]
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    
    if name == "generate_caption":
        from agents.content_creator import ContentCreator
        cc = ContentCreator()
        pillar = arguments.get("pillar", "ootd")
        products = cc.load_affiliate_products()
        caption = cc.generate_dynamic_caption(pillar, products)
        return [types.TextContent(type="text", text=caption)]

    elif name == "get_current_trends":
        from agents.trend_hunter import TrendHunter
        th = TrendHunter()
        trends = th.run()
        return [types.TextContent(type="text", text=json.dumps(trends, indent=2))]

    elif name == "save_diary_entry":
        feeling = arguments.get("feeling")
        diary_path = "content/elina_diary.json"
        
        entries = []
        if os.path.exists(diary_path):
            with open(diary_path, "r") as f:
                try: entries = json.load(f)
                except: pass
                
        entries.append({
            "date": "Now",
            "feeling": feeling
        })
        
        os.makedirs(os.path.dirname(diary_path), exist_ok=True)
        with open(diary_path, "w") as f:
            json.dump(entries[-10:], f, indent=2)
            
        return [types.TextContent(type="text", text=f"Diary entry saved: {feeling}")]

    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    # Run the server using stdin/stdout streams
    import mcp.server.stdio
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ElinaOS",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
