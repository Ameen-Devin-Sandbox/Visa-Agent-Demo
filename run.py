"""Run the Visa Disputes Processing Brain server."""

import uvicorn


def main() -> None:
    """Start the FastAPI server."""
    uvicorn.run(
        "src.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
