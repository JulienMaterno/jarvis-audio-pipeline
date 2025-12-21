"""Deprecated Anthropic model test.

Model discovery now lives in jarvis-intelligence-service.
"""


def main() -> None:  # pragma: no cover
    print(
        "Claude model lookups moved to jarvis-intelligence-service. "
        "Run scripts/debug/test_claude_models.py in that repo instead."
    )


if __name__ == "__main__":
    main()
