"""
discovery.py
------------
UDP peer discovery on port 54321.

  1. On startup:  broadcast PEER_REQUEST.
  2. Forever:     listen on 54321.
       PEER_REQUEST from someone else -> broadcast PEER_ACK (to_node_id = requester)
       PEER_ACK addressed to me       -> connections.connect_to_peer(ip, tcp_port)
  3. Ignore anything whose node_id == my node_id (my own broadcasts).

Why is the ACK broadcast instead of unicast?
  When several nodes run on ONE machine, they all bind UDP 54321 (SO_REUSEADDR).
  The OS delivers a broadcast to every one of them, but a unicast datagram goes to
  only ONE arbitrary socket, which may not be the requester. Broadcasting the ACK
  with a to_node_id field works both on one machine and across machines.
  (Make sure the group agrees on this. It's part of the protocol.)
"""

import socket
import threading

import connections
import logger
import protocol


def create_udp_socket():
    """One UDP socket used for both listening and broadcasting on port 54321."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # many nodes per machine
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)   # allow sending to <broadcast>
    sock.bind(("", protocol.UDP_PORT))
    return sock


def broadcast(node, msg):
    """Send msg to the whole LAN on port 54321 and log it."""
    # TODO: node.udp_sock.sendto(protocol.encode_udp(msg), (protocol.BROADCAST_ADDR, protocol.UDP_PORT))
    #       logger.log_sent("broadcast", msg["type"])
    raise NotImplementedError


def send_peer_request(node):
    """Called once at startup."""
    # TODO: broadcast(node, protocol.make_peer_request(node.node_id))
    raise NotImplementedError


def udp_listener_loop(node):
    """Runs for the lifetime of the node (daemon thread)."""
    while True:
        data, addr = node.udp_sock.recvfrom(protocol.BUFFER_SIZE)
        msg = protocol.decode_udp(data)
        # TODO:
        #   - skip if msg is None or msg["node_id"] == node.node_id   (own broadcast)
        #   - logger.log_received(addr, msg["type"])
        #   - PEER_REQUEST: broadcast(node, make_peer_ack(node.node_id, msg["node_id"], node.tcp_port))
        #   - PEER_ACK and msg["to_node_id"] == node.node_id:
        #         connections.connect_to_peer(node, addr[0], msg["tcp_port"], msg["node_id"])
        #     (connect_to_peer itself refuses duplicates)
        pass


def start_discovery(node):
    """Create the socket, start the listener thread, then announce ourselves."""
    node.udp_sock = create_udp_socket()
    threading.Thread(target=udp_listener_loop, args=(node,), daemon=True).start()
    send_peer_request(node)
