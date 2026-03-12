"""Main entry point for running the Visa Disputes Processing Brain."""

import uvicorn

from visa_disputes_agent.config.settings import get_settings


def main() -> None:
    """Run the dispute processing brain API server."""
    settings = get_settings()
    uvicorn.run(
        "visa_disputes_agent.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
