# Known Limitations

## AI Gateway: TOCTOU Budget Race
Under concurrent requests for the same tenant, two requests that both arrive
before either records cost can both pass the pre-call budget gate simultaneously.
Mitigation: the ceiling estimate provides headroom. Full fix requires a distributed
lock or atomic ledger read-and-reserve, planned for Phase 25.
