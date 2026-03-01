# Known Limitations

## AI Gateway: TOCTOU Budget Race
Under concurrent requests for the same tenant, two requests that both arrive
before either records cost can both pass the pre-call budget gate simultaneously.
Mitigation: the ceiling estimate provides headroom. Full fix requires a distributed
lock or atomic ledger read-and-reserve. The monthly budget hard-block (Phase 25) is
implemented; the TOCTOU window affects only concurrent within-budget requests, not
the block itself.

## Approval Workflow: TTL Read Is Not Atomic

The approval TTL check in `BuildApprovalStore.get_approval()` reads `approved_at`
and computes age at the moment of the call. Under concurrent high-risk build requests
for the same job, two requests arriving within the same millisecond before the first
records a revocation can both read a valid (non-expired) approval.

Mitigation: TTL is enforced on read; approval files are deleted atomically by `unlink()`.
The window is narrow and limited to the TTL check, not approval creation.
Full fix requires a file-level lock on `get_approval()` paired with an expiry write.
