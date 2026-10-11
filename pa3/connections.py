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
    """Accept peers forever, handing each to register_connection()."""
    while True:
        conn, addr = server_sock.accept()
        # TODO: register_connection(node, conn, addr, node_id=None)
        pass


# ------------------------------------------------------------------- client
def connect_to_peer(node, ip, port, node_id):
    """Dial a peer that ACKed our PEER_REQUEST. Must NOT open a second connection.

    TODO:
      - if node.peers.is_connected(node_id): return
      - sock = socket.create_connection((ip, port))
      - register_connection(node, sock, (ip, port), node_id)
    """
    raise NotImplementedError


# ---------------------------------------------------------- shared by both
def register_connection(node, sock, addr, node_id):
    """Common path after connect() or accept():
       add to the peer table -> log PEER ADDED -> send our file list right away
       -> start the receive loop thread.

    TODO
    """
    raise NotImplementedError


def receive_loop(node, peer):
    """Read framed messages from one peer until it disconnects.

    TODO:
      while True:
          try:
              msg = protocol.recv_message(peer.sock)
          except (ConnectionResetError, OSError):
              msg = None
          if msg is None:            # clean close OR died mid-message OR reset
              break
          logging.info(
              "RECEIVED %s:%s %s",
              peer.addr[0],
              peer.addr[1],
              msg.get("type"),
          )
          dispatch(node, peer, msg)
      handle_disconnect(node, peer.key)"""
    
    raise NotImplementedError


def dispatch(node, peer, msg):
    """Route a TCP message by its "type" field to the handlers in file_manager.py."""
    handlers = {
        protocol.FILE_LIST: file_manager.handle_file_list,
        protocol.DATA_REQUEST: file_manager.handle_data_request,
        protocol.FILE_DATA: file_manager.handle_file_data,
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
    handler(node, peer, msg)


def handle_disconnect(node, key):
    """Remove the peer (and its file list) and close the socket. Safe to call twice.

    TODO: peer = node.peers.remove(key); if peer: close socket, log_peer_removed
    """
    raise NotImplementedError
