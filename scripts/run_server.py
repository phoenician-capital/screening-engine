"""
Quick-start script: run the MCP server.

Usage:  python scripts/run_server.py
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.mcp_server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
