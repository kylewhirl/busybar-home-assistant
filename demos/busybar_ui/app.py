"""Run one fake-device UI study directly against BUSY Bar."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
from collections.abc import Sequence

from busylib import AsyncBusyBar

from .icons import APPLICATION_NAME, upload_demo_assets
from .layouts import render_demo
from .models import (
    BaseDemo,
    CapabilitiesDemo,
    DemoView,
    FocusDemo,
    GridDemo,
    parse_input_updates,
)


def _demo(name: str, initial_view: str | None = None) -> BaseDemo:
    demo = {
        "grid": GridDemo,
        "capabilities": CapabilitiesDemo,
        "focus": FocusDemo,
    }[name]()
    allowed = {
        "grid": {DemoView.BROWSE, DemoView.CONTROL},
        "capabilities": {DemoView.BROWSE, DemoView.PROPERTIES, DemoView.EDIT},
        "focus": {DemoView.BROWSE, DemoView.CONTROL},
    }[name]
    if initial_view:
        requested = DemoView(initial_view)
        if requested not in allowed:
            raise ValueError(f"{name!r} does not support the {initial_view!r} view")
        demo.view = requested
    return demo


async def run_demo(
    name: str,
    host: str,
    token: str,
    initial_view: str | None = None,
    *,
    skip_assets: bool = False,
) -> None:
    """Own Canvas until Back or Ctrl-C; fake state stays entirely local."""
    client = AsyncBusyBar(host, token=token)
    demo = _demo(name, initial_view)
    dirty = asyncio.Event()
    stopped = asyncio.Event()

    async def render_loop() -> None:
        while not stopped.is_set():
            await dirty.wait()
            dirty.clear()
            await asyncio.sleep(0.04)
            await client.display_draw(render_demo(demo), sanitize_text=True)

    try:
        if not skip_assets:
            await upload_demo_assets(client)
        await client.display_clear()
        dirty.set()
        renderer = asyncio.create_task(render_loop(), name="BUSY UI demo renderer")
        print(f"Running {name!r}. Dial/Select/Start are live; Back exits.")
        async for message in client.stream_status_ws():
            if not isinstance(message, dict):
                continue
            keep_running = True
            for event_type, value in parse_input_updates(message):
                keep_running = demo.handle(event_type, value)
                dirty.set()
                if not keep_running:
                    break
            if not keep_running:
                break
    finally:
        stopped.set()
        if "renderer" in locals():
            renderer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await renderer
        with contextlib.suppress(Exception):
            await client.display_clear(application_name=APPLICATION_NAME)
        await client.aclose()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--demo", choices=("grid", "capabilities", "focus"), required=True)
    result.add_argument(
        "--view",
        choices=("browse", "control", "properties", "edit"),
        help="Open directly to a view for visual development without sending device input.",
    )
    result.add_argument("--host", default=os.environ.get("BUSY_BAR_ADDR"))
    result.add_argument("--token", default=os.environ.get("BUSY_HTTP_PASSWORD"))
    result.add_argument(
        "--skip-assets",
        action="store_true",
        help="Reuse assets from an earlier demo launch for faster iteration.",
    )
    return result


def main(argv: Sequence[str] | None = None) -> None:
    args = parser().parse_args(argv)
    if not args.host or not args.token:
        raise SystemExit("Set BUSY_BAR_ADDR and BUSY_HTTP_PASSWORD, or pass --host and --token.")
    try:
        asyncio.run(
            run_demo(
                args.demo,
                args.host,
                args.token,
                args.view,
                skip_assets=args.skip_assets,
            )
        )
    except KeyboardInterrupt:
        pass
