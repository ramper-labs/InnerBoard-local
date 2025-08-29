"""
This module provides safety features, including a no-egress guard
to prevent any outbound network connections.
"""
import socket
from contextlib import contextmanager

# Store the original socket connect method
_original_connect = socket.socket.connect

class NetworkAccessBlocked(RuntimeError):
    """Exception raised when a network connection is attempted while blocked."""
    def __init__(self, *args, **kwargs):
        super().__init__("Network access is blocked.")

def _guarded_connect(self, address):
    """Replacement for socket.socket.connect that always raises an exception."""
    raise NetworkAccessBlocked(f"Attempted to connect to {address} with network disabled.")

@contextmanager
def no_network(allow_loopback: bool = False, allowed_ports: tuple = ()):  # type: ignore[override]
    """
    A context manager that blocks all outbound network connections by monkey-patching
    `socket.socket.connect`.

    Args:
        allow_loopback: If True, permit connections to localhost (127.0.0.1, ::1).
        allowed_ports: Optional tuple of port numbers to allow when loopback is permitted.
    """
    def _conditional_connect(self, address):  # type: ignore[override]
        host, port = address
        if allow_loopback:
            try:
                # Fast path for numeric addresses
                is_loopback = host in ("127.0.0.1", "::1") or host.lower() == "localhost"
            except AttributeError:
                is_loopback = False
            if is_loopback and (not allowed_ports or port in allowed_ports):
                return _original_connect(self, address)
        raise NetworkAccessBlocked(f"Attempted to connect to {address} with network disabled.")

    try:
        # Replace the original connect method with our guarded one (conditional if needed)
        socket.socket.connect = _conditional_connect if allow_loopback else _guarded_connect
        yield
    finally:
        # Restore the original connect method
        socket.socket.connect = _original_connect

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
