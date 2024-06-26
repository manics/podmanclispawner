"""Tests for PodmanCLISpawner class"""

# https://github.com/jupyterhub/yarnspawner/blob/0.4.0/yarnspawner/tests/test_spawner.py
import pytest

from jupyterhub.tests.utils import add_user, api_request
from jupyterhub.tests.mocking import public_url
from jupyterhub.tests.utils import async_requests
from jupyterhub.utils import url_path_join
from tornado import gen

from podmanclispawner import PodmanCLISpawner


@pytest.mark.asyncio
async def test_integration(app):
    # Create a user
    add_user(app.db, app, name="alice")
    alice = app.users["alice"]
    assert isinstance(alice.spawner, PodmanCLISpawner)
    token = alice.new_api_token()

    # Not started, status should be 0
    status = await alice.spawner.poll()
    assert status == 0

    # Stop can be called before start, no-op
    await alice.spawner.stop()

    # Start the server, and wait for it to start
    resp = None
    while resp is None or resp.status_code == 202:
        await gen.sleep(2.0)
        resp = await api_request(app, "users", "alice", "server", method="post")
    # https://github.com/jupyterhub/jupyterhub/blob/1.1.0/docs/rest-api.yml#L236-L259
    # https://github.com/jupyterhub/jupyterhub/blob/1.1.0/jupyterhub/apihandlers/users.py#L411
    assert resp.ok or resp.json() == {
        "status": 400,
        "message": "alice is already running",
    }

    # check progress events were emitted
    count = 0
    async for e in alice.spawner.progress():
        count += 1
    assert count >= 1

    # Check that everything is running fine
    url = url_path_join(public_url(app, alice), "api/status")
    resp = await async_requests.get(url, headers={"Authorization": "token %s" % token})
    resp.raise_for_status()
    assert "kernels" in resp.json()

    # Save the app_id to use later
    # app_id = alice.spawner.app_id

    # Shutdown the server
    resp = await api_request(app, "users", "alice", "server", method="delete")
    resp.raise_for_status()

    # Check status
    status = await alice.spawner.poll()
    assert status == 0
