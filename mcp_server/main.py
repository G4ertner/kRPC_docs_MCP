from . import tools  # noqa: F401 - ensure tools are registered
from . import wiki_tools  # noqa: F401 - register KSP Wiki tools
from . import resources  # noqa: F401 - register playbook resources
from . import prompts    # noqa: F401 - register master prompt
from .krpc import tools as krpc_tools  # noqa: F401 - register kRPC tools
from . import executor_tools  # noqa: F401 - register execute_script tool
from . import blueprint_cache  # noqa: F401 - register blueprint resource
from . import blueprint_export  # noqa: F401 - register export tool
from . import snippets_tools  # noqa: F401 - register snippet search/resolve tools
from .server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
