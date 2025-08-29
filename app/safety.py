"""
This module provides safety features, including a no-egress guard
to prevent any outbound network connections.
"""

import socket
import ipaddress
from contextlib import contextmanager
from typing import Tuple, Optional
from app.config import config
from app.logging_config import get_logger
from app.exceptions import NetworkAccessBlocked

logger = get_logger(__name__)

# Store the original socket connect method
_original_connect = socket.socket.connect


def _is_loopback_address(host: str) -> bool:
    """Check if a host is a loopback address."""
    try:
        # Handle string hostnames
        if host.lower() in ("localhost", "localhost.localdomain"):
            return True

        # Handle IP addresses
        ip = ipaddress.ip_address(host)
        return ip.is_loopback
    except (ipaddress.AddressValueError, ValueError):
        # If we can't parse it as an IP, try to resolve it
        try:
            resolved = socket.gethostbyname(host)
            ip = ipaddress.ip_address(resolved)
            return ip.is_loopback
        except (socket.gaierror, ipaddress.AddressValueError):
            return False


def _guarded_connect(self, address):
    """Replacement for socket.socket.connect that always raises an exception."""
    raise NetworkAccessBlocked(
        f"Attempted to connect to {address} with network disabled."
    )


@contextmanager
def no_network(
    allow_loopback: Optional[bool] = None,
    allowed_ports: Optional[Tuple[int, ...]] = None,
):
    """
    A context manager that blocks all outbound network connections by monkey-patching
    `socket.socket.connect`.

    Args:
        allow_loopback: If True, permit connections to localhost (127.0.0.1, ::1).
                       Defaults to config value.
        allowed_ports: Tuple of port numbers to allow when loopback is permitted.
                      Defaults to config value.
    """
    # Use config defaults if not specified
    allow_loopback = (
        allow_loopback if allow_loopback is not None else config.allow_loopback
    )
    allowed_ports = allowed_ports if allowed_ports is not None else config.allowed_ports

    logger.info(
        f"Enabling network guard (loopback={allow_loopback}, ports={allowed_ports})"
    )

    def _conditional_connect(self, address):
        # Handle different address formats robustly
        if isinstance(address, tuple) and len(address) >= 2:
            host, port = address[0], address[1]
        elif isinstance(address, str):
            # Handle string addresses (e.g., Unix sockets)
            host, port = address, None
        else:
            # Fallback for unknown formats
            host, port = str(address), None

        if allow_loopback and host and _is_loopback_address(host):
            if not allowed_ports or (port is not None and port in allowed_ports):
                logger.debug(f"Allowing loopback connection to {address}")
                return _original_connect(self, address)

        logger.warning(f"Blocking network connection to {address}")
        raise NetworkAccessBlocked(
            f"Attempted to connect to {address} with network disabled."
        )

    try:
        # Replace the original connect method with our guarded one
        socket.socket.connect = (
            _conditional_connect if allow_loopback else _guarded_connect
        )
        yield
    finally:
        # Restore the original connect method
        socket.socket.connect = _original_connect
        logger.info("Network guard disabled")


def main():
    """Demonstrates the no_network context manager."""
    print("Testing network access without guard:")
    try:
        # This should succeed if you have an internet connection
        socket.create_connection(("8.8.8.8", 53), timeout=1)
        print("-> Connection successful (as expected).")
    except (socket.timeout, socket.gaierror, OSError) as e:
        print(f"-> Connection failed, but not because of the guard: {e}")

    print("\nTesting network access WITH the no_network guard:")
    with no_network():
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=1)
            print("-> UNEXPECTED: Connection was not blocked!")
        except NetworkAccessBlocked as e:
            print(f"-> SUCCESS: {e}")
        except Exception as e:
            print(f"-> UNEXPECTED ERROR: Caught {type(e).__name__}: {e}")

    print("\nVerifying network access is restored after exiting context:")
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=1)
        print("-> Connection successful (as expected).")
    except (socket.timeout, socket.gaierror, OSError) as e:
        print(f"-> Connection failed, but not because of the guard: {e}")


if __name__ == "__main__":
    main()
