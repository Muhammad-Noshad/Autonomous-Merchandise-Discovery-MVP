"""Stage sequencing, retry, resume, and workflow-state coordination.

The orchestrator owns control flow while each stage module owns one semantic transformation. This
prevents stage files from becoming tightly coupled to UI, persistence, or model-provider details.
"""

