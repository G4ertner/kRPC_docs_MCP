from . import tools  # noqa: F401 - ensure tools are registered
from . import wiki_tools  # noqa: F401 - register KSP Wiki tools
from . import resources  # noqa: F401 - register playbook resources
from .krpc import tools as krpc_tools  # noqa: F401 - register kRPC tools
from .server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
