"""Application service for starting and inspecting discovery runs.

This layer coordinates use cases; it should not contain Streamlit rendering or raw MongoDB query
syntax. Those concerns remain behind the entrypoint and repository boundaries.
"""

