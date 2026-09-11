"""Streamlit entrypoint for the internal merchandise discovery dashboard.

This file stays intentionally thin: the UI entrypoint delegates to the packaged application so
the workflow can later be reused by a worker or an HTTP API without importing Streamlit.
"""

from merchandise_discovery.entrypoints.streamlit_app import main

if __name__ == "__main__":
    main()

