"""
logger.py
---------
Thread-safe logging to <node dir>/log.txt (and to the console).

Required by the assignment:
  * every message sent/received: timestamp, direction, peer address, message type
  * peer table changes: peer added (after connect), peer removed (after disconnect)
"""

import threading
from datetime import datetime

_log_lock = threading.Lock()
_log_path = "log.txt"


def init_log(path):
    """Set the log file path and truncate it at startup."""
    global _log_path
    _log_path = path
    # TODO: open(path, "w") to clear the old log


def _write(line):
    """Prefix a timestamp, print it, and append it to the log file (under the lock)."""
    # TODO: timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    #       with _log_lock: print + append f"[{timestamp}] {line}\n"
    raise NotImplementedError


def log_sent(addr, msg_type):
    """e.g.  [ts] SENT     192.168.1.5:6001  FILE_LIST"""
    # TODO: _write(...)
    raise NotImplementedError


def log_received(addr, msg_type):
    # TODO
    raise NotImplementedError


def log_peer_added(addr, node_id):
    """e.g.  [ts] PEER ADDED    192.168.1.5:6001  node=1a2b..."""
    # TODO
    raise NotImplementedError


def log_peer_removed(addr, node_id):
    # TODO
    raise NotImplementedError


def log_info(text):
    """Anything else (startup, errors, download complete, ...)."""
    # TODO
    raise NotImplementedError
