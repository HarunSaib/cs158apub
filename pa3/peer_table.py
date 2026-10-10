"""
peer_table.py
-------------
Thread-safe table of connected peers and the files each one advertises.

Read/written by: the accept thread, each receive loop, the file-list timer,
the UDP listener (duplicate check) and the CLI. Every method takes self.lock.

Key = the "ip:port" string of the TCP connection (known on both sides right away).
node_id is filled in from the ACK (client side) or the first message (server side).
"""

import threading


class Peer:
    """One connected peer."""

    def __init__(self, sock, addr, node_id=None):
        self.sock = sock
        self.addr = addr                    # (ip, port) tuple
        self.node_id = node_id              # sender UUID, may be None at first
        self.files = set()                  # filenames from its latest FILE_LIST
        self.send_lock = threading.Lock()   # serializes sendall() on this socket

    @property
    def key(self):
        return f"{self.addr[0]}:{self.addr[1]}"


class PeerTable:
    def __init__(self):
        self.lock = threading.Lock()
        self.peers = {}                 # key -> Peer

    def add(self, peer):
        """Insert a newly connected peer. Return False if that node_id is already connected."""
        # TODO
        raise NotImplementedError

    def remove(self, key):
        """Delete and return the Peer (or None). Its file list goes with it."""
        # TODO
        raise NotImplementedError

    def get(self, key):
        # TODO
        raise NotImplementedError

    def is_connected(self, node_id):
        """True if any connected peer has this node_id."""
        # TODO
        raise NotImplementedError

    def update_files(self, key, node_id, filenames):
        """Replace a peer's advertised list (and record its node_id if still unknown)."""
        # TODO
        raise NotImplementedError

    def all_peers(self):
        """Snapshot list of Peer objects, safe to iterate without the lock."""
        # TODO: return list(self.peers.values())  (under the lock)
        raise NotImplementedError

    def snapshot(self):
        """{key: sorted list of files} for printing in the CLI."""
        # TODO
        raise NotImplementedError
