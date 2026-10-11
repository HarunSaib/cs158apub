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
    out = []
    for root, dirs, files in os.walk(node.shared_dir):
        root = os.path.relpath(root, node.shared_dir)
        if os.pathsep != '/':
            root = root.replace(os.pathsep, '/')
        for file in files:
            out.append(f'{root}/{file}')
    out.sort()
    return out


def has_file(node, filename):
    # TODO maybe return False for hidden files also, to prevent peers downloading them?
    return '../' not in filename and '..\\' not in filename and os.path.exists(os.path.join(node.shared_dir, filename))

# ------------------------------------------------------- periodic file list
def broadcast_file_list(node, force=False):
    """Send our current FILE_LIST to every connected peer."""
    file_list = list_shared(node)
    if file_list != node.last_shared_list or force:
        logger.log_info('broadcasting updated file list')
        msg = protocol.make_file_list(node.node_id, list_shared(node))
        for peer in node.peers.all_peers():
            connections.send_to_peer(node, peer, msg)
        node.last_shared_list = file_list
        return True
    return False



def file_list_loop(node):
    while True:
        time.sleep(FILE_LIST_INTERVAL)
        broadcast_file_list(node)


def start_file_list_broadcaster(node):
    threading.Thread(target=file_list_loop, args=(node,), daemon=True).start()


# ------------------------------------------------------------- TCP handlers
def handle_file_list(node, peer, msg):
    """Replace this peer's entry in the peer table."""
    logger.log_info(f'received updated file list from {peer.key} (node ID {msg['node_id']}')
    node.peers.update_files(peer.key, msg["node_id"], msg["files"])


def handle_data_request(node, peer, msg):
    """Serve the file, or reply with an error FILE_DATA if it's gone or invalid.

    TODO:
      name = msg["filename"]
      if not has_file(node, name): send make_file_error(...)
      else: read bytes from shared/ and send make_file_data(...)
      (use connections.send_to_peer)
    """
    name = msg["filename"]
    if has_file(node, name):
        try:
            with open(os.path.join(node.shared_dir, name), 'rb') as f:
                while data := f.read(8192):
                    packet = protocol.make_file_data(node.node_id, name, data)
                    connections.send_to_peer(node, peer, packet)
                connections.send_to_peer(node, peer, protocol.make_file_end(node.node_id, name))
        except Exception as e:
            connections.send_to_peer(node, peer, protocol.make_file_error(node.node_id, name, str(e)))
    else:
        connections.send_to_peer(node, peer, protocol.make_file_error(node.node_id, name, 'File not found'))


def handle_file_data(node, peer, msg):
    """Save a downloaded file, or report the error.

    TODO:
      - status ERROR -> logger.log_info(...) and return
      - data = protocol.decode_content(msg["content"])
      - write to downloads/<name>, THEN shutil.copy into shared/<name>
    """
    name = msg['name']
    if msg['status'] == 'OK':
        file = node.receiving_files[name] # this line will raise KeyError if we got file data for a file we did not request
        if file is None:
            file = node.receiving_files[name] = open(os.path.join(node.downloads_dir, name+'.part'), 'wb')
        data = protocol.decode_content(msg['content'])
        logger.log_info(f'received {len(data)} bytes for file {name}')
        file.write(data)
    else:
        logger.log_info(f'peer returned error for file {name}: {msg['message']}')
        handle_file_error(node, peer, msg)

def handle_file_end(node, peer, msg):
    name = msg["name"]
    file = node.receiving_files.pop(name)
    if file is not None:
        path = os.path.join(node.downloads_dir, name)
        os.rename(path+'.part', path)

def handle_file_error(node, peer, msg):
    """This returns None and should be called *in addition* to displaying the error message to the user."""
    name = msg["name"]
    file = node.receiving_files.pop(name)
    if file is not None:
        file.close()
        path = os.path.join(node.downloads_dir, name)
        os.rename(path+'.part', path+'.corrupted')

# ---------------------------------------------------------- user requests
def request_file(node, peer_key, filename):
    """Called by the CLI. Returns a short status string to print.

    TODO:
      - refuse if has_file(node, filename)           ("already have it")
      - peer = node.peers.get(peer_key); refuse if None
      - send make_data_request(...)
    """
    if filename in node.receiving_files:
        # XXX this leaves us vulnerable to a DoS if the peer does not promptly respond with either data or error.
        return 'already downloading a file with that name, please wait for it to finish'
    if peer_key not in node.peers:
        return 'no such peer'
    node.receiving_files[filename] = None # will be replaced with a file object upon the first handle_file_data
    connections.send_to_peer(node, peer, protocol.make_data_request(node_id, filename))
