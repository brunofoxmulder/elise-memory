"""Executable entry point for the isolated Élise Memory service."""

import os

import uvicorn


def main() -> None:
    host = os.getenv("ELISE_MEMORY_HOST", "0.0.0.0")
    port = int(os.getenv("ELISE_MEMORY_PORT", "8099"))
    uvicorn.run("elise_memory.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
