"""App-level CLI handlers (API server)."""

from __future__ import annotations

from rich.console import Console


def _run_api_server(args, console: Console) -> int:
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[bold red]error:[/] install API dependencies with "
            "`pip install -e .[api]`"
        )
        return 1

    host = getattr(args, "host", "127.0.0.1")
    port = int(getattr(args, "port", 8000))
    console.print(f"[green]Starting CoinFox API[/] at http://{host}:{port}")
    uvicorn.run(
        "coinfox.api:app",
        host=host,
        port=port,
        reload=bool(getattr(args, "reload", False)),
    )
    return 0
