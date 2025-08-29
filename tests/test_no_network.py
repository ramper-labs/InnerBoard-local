"""
Tests the no-egress guard from app.safety.
"""

import pytest
import socket
import requests
from app.safety import no_network, NetworkAccessBlocked


def test_no_network_blocks_socket_connection():
    """
    Ensures that socket.socket.connect is blocked within the no_network context.
    """
    with pytest.raises(NetworkAccessBlocked):
        with no_network():
            # Use a common address for testing, e.g., Google's DNS
            socket.create_connection(("8.8.8.8", 53), timeout=1)


def test_network_is_restored_after_context():
    """
    Ensures that network access is restored after the context manager exits.
    """
    try:
        # This test requires an active internet connection to pass reliably.
        # If it fails, it might be due to a lack of connectivity.
        socket.create_connection(("8.8.8.8", 53), timeout=1)
        network_available = True
    except (socket.timeout, socket.gaierror, OSError):
        network_available = False

    if not network_available:
        pytest.skip("No internet connection available to test network restoration.")

    # Within the context, it should fail
    with pytest.raises(NetworkAccessBlocked):
        with no_network():
            socket.create_connection(("8.8.8.8", 53), timeout=1)

    # Outside the context, it should succeed again
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=1)
        assert True
    except (socket.timeout, socket.gaierror, OSError) as e:
        pytest.fail(f"Network connection failed after context exit: {e}")


def test_no_network_blocks_higher_level_libraries():
    """
    Ensures that libraries like 'requests' are also blocked.
    """
    with pytest.raises(NetworkAccessBlocked):
        with no_network():
            try:
                # This will eventually call socket.connect()
                requests.get("https://www.google.com", timeout=1)
            except requests.exceptions.RequestException as e:
                # We need to check if the underlying cause is our custom exception
                if not isinstance(e.__cause__, NetworkAccessBlocked):
                    pytest.fail(
                        f"Request failed but not due to NetworkAccessBlocked. Cause: {e.__cause__}"
                    )
                else:
                    # This is the expected path. Re-raise our exception to satisfy pytest.raises.
                    raise e.__cause__
