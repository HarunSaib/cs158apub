"""
file_manager.py
---------------
Everything about files:
  * listing shared/
  * the 10-second file-list broadcaster
  * handlers for FILE_LIST, DATA_REQUEST, FILE_DATA (called by connections.dispatch)
  * requesting a download (called by the CLI)
  * saving downloads: write to downloads/ FIRST, copy to shared/ when complete
"""

import os
import shutil
import threading
import time

import connections
import logger
import protocol

FILE_LIST_INTERVAL = 10   # seconds


# ------------------------------------------------------------ local storage
def list_shared(node):
    """Sorted names of regular files in shared/ (names only, no paths)."""
    # TODO
    raise NotImplementedError


def has_file(node, filename):
    # TODO
    raise NotImplementedError


# ------------------------------------------------------- periodic file list
def broadcast_file_list(node):
    """Send our current FILE_LIST to every connected peer."""
    msg = protocol.make_file_list(node.node_id, list_shared(node))
    for peer in node.peers.all_peers():
        connections.send_to_peer(node, peer, msg)


def file_list_loop(node):
    while True:
        time.sleep(FILE_LIST_INTERVAL)
        broadcast_file_list(node)


def start_file_list_broadcaster(node):
    threading.Thread(target=file_list_loop, args=(node,), daemon=True).start()


# ------------------------------------------------------------- TCP handlers
def handle_file_list(node, peer, msg):
    """Replace this peer's entry in the peer table."""
    # TODO: node.peers.update_files(peer.key, msg["node_id"], msg["files"])
    raise NotImplementedError


def handle_data_request(node, peer, msg):
    """Serve the file, or reply with an error FILE_DATA if it's gone or invalid.

    TODO:
      name = msg["filename"]
      if not has_file(node, name): send make_file_error(...)
      else: read bytes from shared/ and send make_file_data(...)
      (use connections.send_to_peer)
    """
    raise NotImplementedError


def handle_file_data(node, peer, msg):
    """Save a downloaded file, or report the error.

    TODO:
      - status ERROR -> logger.log_info(...) and return
      - data = protocol.decode_content(msg["content"])
      - write to downloads/<name>, THEN shutil.copy into shared/<name>
    """
    raise NotImplementedError


# ---------------------------------------------------------- user requests
def request_file(node, peer_key, filename):
    """Called by the CLI. Returns a short status string to print.

    TODO:
      - refuse if has_file(node, filename)           ("already have it")
      - peer = node.peers.get(peer_key); refuse if None
      - send make_data_request(...)
    """
    raise NotImplementedError
