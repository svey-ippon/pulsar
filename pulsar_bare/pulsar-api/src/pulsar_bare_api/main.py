from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "pulsar_bare_api.app:app",
        host=os.environ.get("PULSAR_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("PULSAR_API_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
