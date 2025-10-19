from . import tools  # noqa: F401 - ensure tools are registered
from .server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

