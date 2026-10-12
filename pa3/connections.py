"""
connections.py
--------------
TCP connection management.

  * start_tcp_server : bind our TCP port and run the accept loop (we are the server
                       for nodes that join after us)
  * connect_to_peer  : called by discovery after a PEER_ACK (the new node is the client)
  * receive_loop     : one thread per peer; reads framed messages and dispatches them
  * handle_disconnect: empty recv / reset -> remove peer + its files, close the socket
"""

import socket
import threading
import logging
import file_manager
import protocol
from peer_table import Peer


# ------------------------------------------------------------------ sending
def send_to_peer(node, peer, msg):
    """Send one message to a peer and log it. On failure, treat it as a disconnect."""
    try:
        protocol.send_message(peer.sock, msg, peer.send_lock)
        
        logging.info(
            "SENT %s:%s %s",
            peer.addr[0],
            peer.addr[1],
            msg["type"],
        )
        
    except OSError:
        handle_disconnect(node, peer.key)


# ------------------------------------------------------------------- server
def start_tcp_server(node):
    """Bind node.tcp_port and start the accept-loop thread."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("", node.tcp_port))
    server_sock.listen(5)
    threading.Thread(target=accept_loop, args=(node, server_sock), daemon=True).start()


def accept_loop(node, server_sock):
    """Accept peers forever, handing each to register_connection().
    The accepting side doesn't know the peer's node_id yet; it arrives in the peer's first FILE_LIST."""
    while True:
        conn, addr = server_sock.accept()
        register_connection(node, conn, addr, None)


# ------------------------------------------------------------------- client
CONNECT_TIMEOUT = 5   # seconds; this runs on the UDP listener thread, so don't block discovery for long

def connect_to_peer(node, ip, port, node_id):
    """Dial a peer that ACKed our PEER_REQUEST. Must NOT open a second connection."""
    if node.peers.is_connected(node_id):
        return
    try:
        sock = socket.create_connection((ip, port), timeout=CONNECT_TIMEOUT)
    except OSError as exc:
        logging.info("Could not connect to %s:%s: %s", ip, port, exc)
        return
    sock.settimeout(None)                       # back to blocking for the receive loop
    register_connection(node, sock, (ip, port), node_id)


# ---------------------------------------------------------- shared by both
def register_connection(node, sock, addr, node_id):
    """Common path after connect() or accept():
       add to the peer table -> log PEER ADDED -> send our file list right away
       -> start the receive loop thread."""
    peer = Peer(sock, addr, node_id)
    if not node.peers.add(peer):                # already connected to this node
        sock.close()
        return

    logging.info("PEER ADDED %s:%s node=%s", addr[0], addr[1], node_id)

    # Send the first file list directly, rather than waiting up to 10 s for the timer.
    send_to_peer(node, peer, protocol.make_file_list(node.node_id, file_manager.list_shared(node)))

    threading.Thread(target=receive_loop, args=(node, peer), daemon=True).start()


def receive_loop(node, peer):
    """Read framed messages from one peer until it disconnects."""
    while True:
        try:
            msg = protocol.recv_message(peer.sock)
        except (OSError, ValueError):           # reset/closed socket, or a garbled frame (bad JSON)
            msg = None
        if msg is None:                         # clean close OR died mid-message OR reset
            break

        logging.info("RECEIVED %s:%s %s", peer.addr[0], peer.addr[1], msg.get("type"))

        try:
            dispatch(node, peer, msg)
        except Exception:                       # a handler bug shouldn't kill this peer's connection
            logging.exception("Error handling %s from %s:%s", msg.get("type"), peer.addr[0], peer.addr[1])

    handle_disconnect(node, peer.key)


def dispatch(node, peer, msg):
    """Route a TCP message by its "type" field to the handlers in file_manager.py."""
    handlers = {
        protocol.FILE_LIST: file_manager.handle_file_list,
        protocol.DATA_REQUEST: file_manager.handle_data_request,
        protocol.FILE_DATA: file_manager.handle_file_data,
        protocol.FILE_END: file_manager.handle_file_end,
    }
    handler = handlers.get(msg.get("type"))
    if handler is None:
        logging.info(
            "Unknown message type from %s:%s: %s",
            peer.addr[0],
            peer.addr[1],
            msg.get("type"),
        )
        return
    if handler is file_manager.handle_data_request:
        """ Serving a file can take a while, do it on its own thread so this node's
        receive loop keeps reading. Otherwise two peers sending each other large
        files at the same time both stop reading and their sendall() calls block forever. """
        threading.Thread(target=handler, args=(node, peer, msg), daemon=True).start()
    else:
        handler(node, peer, msg)


def handle_disconnect(node, key):
    """Remove the peer (and its file list) and close the socket. Safe to call twice."""
    peer = node.peers.remove(key)
    if peer is None:                            # already handled (e.g. by send_to_peer and receive_loop)
        return
    try:
        peer.sock.close()
    except OSError:
        pass
    logging.info("PEER REMOVED %s:%s node=%s", peer.addr[0], peer.addr[1], peer.node_id)