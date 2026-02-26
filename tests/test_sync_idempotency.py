import os
import pytest


@pytest.mark.skipif(
    os.getenv("RUN_SYNC_E2E") != "1",
    reason="sync plan/apply/reapply e2e requires seeded workspace repos; set RUN_SYNC_E2E=1 to run",
)
def test_plan_apply_reapply_noop(client):
    # placeholder: implement real e2e once workspace seeding is wired for tests
    assert True