"""Entry point for `python -m pulsar_bare_ui` and the `pulsar-bare-ui` console script.

Resolves the Streamlit script path from the installed package so the app can be launched without
knowing the filesystem layout:

    python -m pulsar_bare_ui
    uv run pulsar-bare-ui
    pulsar-bare-ui --server.port=8502

Extra CLI arguments are forwarded to `streamlit run` unchanged.
"""

from __future__ import annotations

import sys
from importlib.resources import files


def main() -> None:
    from streamlit.web import cli as stcli  # imported lazily — fast __main__ startup

    main_py = str(files("pulsar_bare_ui").joinpath("main.py"))

    sys.argv = ["streamlit", "run", main_py, "--server.address=0.0.0.0"] + sys.argv[1:]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
