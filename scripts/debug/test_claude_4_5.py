"""Deprecated Anthropic test script.

The audio pipeline no longer connects to Claude directly. Use the
jarvis-intelligence-service repository to validate model availability.
"""


def main() -> None:  # pragma: no cover - informational script
    print(
        "This script is deprecated. Run intelligence service debug tools instead "
        "(scripts/debug/test_claude_*.py in jarvis-intelligence-service)."
    )


if __name__ == "__main__":
    main()
