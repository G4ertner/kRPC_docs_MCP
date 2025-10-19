from mcp.server.fastmcp import FastMCP

# Shared FastMCP server instance
mcp = FastMCP("krpc_docs")

if __name__ == "__main__":
    mcp.run()

