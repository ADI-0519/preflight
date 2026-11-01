from typing import Annotated

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field
from pydantic.fields import FieldInfo

from preflight.agent.tools import TOOLS, Toolbox

BY_NAME = {t["name"]: t for t in TOOLS}


def described(tool: str, argument: str) -> FieldInfo:
    return Field(description=BY_NAME[tool]["parameters"]["properties"][argument]["description"])


def build_server(toolbox: Toolbox | None = None) -> FastMCP:
    server = FastMCP("preflight")

    def shared() -> Toolbox:
        nonlocal toolbox
        # built on the first call so the server starts without keys
        if toolbox is None:
            from preflight.check.precedents import load_precedents
            from preflight.models import from_env
            from preflight.pipeline import SNAPSHOTS

            toolbox = Toolbox(from_env(), load_precedents(SNAPSHOTS.rulings))
        return toolbox

    async def run(name: str, arguments: dict) -> dict:
        # a screening blocks for minutes and page capture uses Playwright's sync API, so both stay off the event loop
        result = await anyio.to_thread.run_sync(lambda: shared().call(name, arguments))
        if "error" in result:
            raise ToolError(result["error"])
        return result

    @server.tool(name="screen_ad", description=BY_NAME["screen_ad"]["description"])
    async def screen_ad(target: Annotated[str, described("screen_ad", "target")]) -> dict:
        return await run("screen_ad", {"target": target})

    @server.tool(name="fix_ad", description=BY_NAME["fix_ad"]["description"])
    async def fix_ad(draft: Annotated[str, described("fix_ad", "draft")]) -> dict:
        return await run("fix_ad", {"draft": draft})

    return server


def main() -> None:
    build_server().run("stdio")
