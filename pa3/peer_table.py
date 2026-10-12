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

    def _has_node_id(self, node_id):
        """True if a stored peer has this node_id. Caller must already hold self.lock."""
        return node_id is not None and any(p.node_id == node_id for p in self.peers.values())

    def add(self, peer):
        """Insert a newly connected peer. Return False if that node_id (or key) is already connected."""
        with self.lock:
            if peer.key in self.peers or self._has_node_id(peer.node_id):
                return False
            self.peers[peer.key] = peer
            return True

    def remove(self, key):
        """Delete and return the Peer (or None). Its file list goes with it."""
        with self.lock:
            return self.peers.pop(key, None)

    def get(self, key):
        """The Peer stored under key, or None."""
        with self.lock:
            return self.peers.get(key)

    def is_connected(self, node_id):
        """True if any connected peer has this node_id."""
        with self.lock:
            return self._has_node_id(node_id)

    def update_files(self, key, node_id, filenames):
        """Replace a peer's advertised list (and record its node_id if still unknown)."""
        with self.lock:
            peer = self.peers.get(key)
            if peer is None:                # peer disconnected while its message was being handled
                return
            peer.files = set(filenames)
            if peer.node_id is None:        # server side learns the id from the first message
                peer.node_id = node_id

    def all_peers(self):
        """Snapshot list of Peer objects, safe to iterate without the lock."""
        with self.lock:
            return list(self.peers.values())

    def snapshot(self):
        """{key: sorted list of files} for printing in the CLI."""
        with self.lock:
            return {key: sorted(peer.files) for key, peer in self.peers.items()}