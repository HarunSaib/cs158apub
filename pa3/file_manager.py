"""
file_manager.py
---------------
Everything about files:
  * listing shared/
  * the 10-second file-list broadcaster
  * handlers for FILE_LIST, DATA_REQUEST, FILE_DATA, FILE_END (called by connections.dispatch)
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
CHUNK_SIZE = 8192         # bytes of file content per FILE_DATA message


# ------------------------------------------------------------ local storage
def list_shared(node):
    """Sorted names of regular files in shared/ (names only, no paths, no subfolders)."""
    return sorted(f for f in os.listdir(node.shared_dir)
                  if os.path.isfile(os.path.join(node.shared_dir, f)))

def has_file(node, filename):
    """True if shared/<filename> is a regular file.

    Rejects anything that isn't a plain name (e.g. '../x' or 'C:\\x'), so a peer
    can't request files outside shared/.
    """
    return (os.path.basename(filename) == filename
            and os.path.isfile(os.path.join(node.shared_dir, filename)))

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
    logger.log_info(f'received updated file list from {peer.key} (node ID {msg["node_id"]})')
    node.peers.update_files(peer.key, msg["node_id"], msg["files"])

def handle_data_request(node, peer, msg):
    """Serve the file as CHUNK_SIZE FILE_DATA messages followed by FILE_END,
    or reply with an error FILE_DATA if it's gone or invalid."""
    name = msg["filename"]
    if has_file(node, name):
        try:
            with open(os.path.join(node.shared_dir, name), 'rb') as f:
                while data := f.read(CHUNK_SIZE):
                    packet = protocol.make_file_data(node.node_id, name, data)
                    connections.send_to_peer(node, peer, packet)
                connections.send_to_peer(node, peer, protocol.make_file_end(node.node_id, name))
        except Exception as e:
            connections.send_to_peer(node, peer, protocol.make_file_error(node.node_id, name, str(e)))
    else:
        connections.send_to_peer(node, peer, protocol.make_file_error(node.node_id, name, 'File not found'))

def handle_file_data(node, peer, msg):
    """Append one chunk of a requested file to downloads/<name>.part, or handle an error reply."""
    name = msg["filename"]
    if msg["status"] != protocol.STATUS_OK:
        logger.log_info(f'peer returned error for file {name}: {msg.get("error")}')
        handle_file_error(node, peer, msg)
        return
    if name not in node.receiving_files:
        return                                   # we never requested this file; ignore it
    file = node.receiving_files[name]
    if file is None:                             # first chunk: open the partial file
        file = node.receiving_files[name] = open(os.path.join(node.downloads_dir, name + '.part'), 'wb')
    data = protocol.decode_content(msg["content"])
    logger.log_info(f'received {len(data)} bytes for file {name}')
    file.write(data)

def handle_file_end(node, peer, msg):
    """All chunks received: finish the file in downloads/, then copy it into shared/."""
    name = msg["filename"]
    if name not in node.receiving_files:
        return                                   # we never requested this file; ignore it
    file = node.receiving_files.pop(name)
    path = os.path.join(node.downloads_dir, name)
    if file is None:                             # 0-byte file: no FILE_DATA ever arrived
        open(path + '.part', 'wb').close()
    else:
        file.close()                             # flush and release before renaming (required on Windows)
    os.replace(path + '.part', path)             # complete in downloads/ first...
    shutil.copy(path, os.path.join(node.shared_dir, name))   # ...then share it
    logger.log_info(f'download complete: {name}')

def handle_file_error(node, peer, msg):
    """Stop tracking a failed download. Any partial data is kept as <name>.corrupted.

    Returns None; the caller is responsible for reporting the error.
    """
    name = msg["filename"]
    file = node.receiving_files.pop(name, None)
    if file is not None:
        file.close()
        path = os.path.join(node.downloads_dir, name)
        os.replace(path + '.part', path + '.corrupted')

# ---------------------------------------------------------- user requests
def request_file(node, peer_key, filename):
    """Called by the CLI. Sends a DATA_REQUEST and returns a short status string to print.

    The file itself arrives later on that peer's receive thread (handle_file_data / handle_file_end).
    """
    if has_file(node, filename):
        return 'already have that file in shared/'
    if filename in node.receiving_files:
        # XXX this leaves us vulnerable to a DoS if the peer does not promptly respond with either data or error.
        return 'already downloading a file with that name, please wait for it to finish'
    peer = node.peers.get(peer_key)
    if peer is None:
        return 'no such peer'
    node.receiving_files[filename] = None # will be replaced with a file object upon the first handle_file_data
    connections.send_to_peer(node, peer, protocol.make_data_request(node.node_id, filename))
    return f'requested {filename} from {peer_key}'
