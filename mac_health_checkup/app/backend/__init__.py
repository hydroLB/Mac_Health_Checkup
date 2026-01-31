"""
Summary
Provide backend interfaces used by non-Python frontends.

Inputs
None.

Outputs
Exports backend helpers for snapshot-style UI integrations.

Side effects
None.

Error handling
None.

Ties to other methods
Used by the SwiftUI app to fetch a JSON snapshot via the Python entrypoint.

Why this exists
Keeps frontend integration code isolated from the Tk and CLI rendering hosts.
"""
