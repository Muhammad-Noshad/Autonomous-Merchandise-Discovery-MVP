"""Worker entrypoint reserved for durable background workflow execution.

The worker will claim pending workflow runs from MongoDB and execute stages independently of the
Streamlit request lifecycle. Keeping this entrypoint separate prevents long AI calls from becoming
coupled to a browser session.
"""

from merchandise_discovery.entrypoints.worker import main

if __name__ == "__main__":
    main()

