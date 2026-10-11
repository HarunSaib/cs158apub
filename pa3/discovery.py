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
import protocol
import logging


def create_udp_socket():
    """One UDP socket used for both listening and broadcasting on port 54321."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # many nodes per machine
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)   # allow sending to <broadcast>
    sock.bind(("", protocol.UDP_PORT))
    return sock


def broadcast(node, msg):
    """Send msg to the whole LAN on port 54321 and log it."""
    
    try:
        node.udp_sock.sendto(
            protocol.encode_udp(msg),
            (protocol.BROADCAST_ADDR, protocol.UDP_PORT)
        )

    except OSError as exc:
        logging.info("Could not broadcast %s: %s", msg["type"], exc)
        return False

    # log that the msg was sent
    logging.info("SENT broadcast %s", msg["type"])
    return True


def send_peer_request(node):
    """Called once at startup."""
    broadcast(node, protocol.make_peer_request(node.node_id))


def udp_listener_loop(node):
    """Runs for the lifetime of the node (daemon thread)."""

    # continuously wait for discovery msgs
    while True:
        
        try:
            data, addr = node.udp_sock.recvfrom(protocol.BUFFER_SIZE)

        except OSError:
            return 
        
        msg = protocol.decode_udp(data)

        # don't respond to invalid msgs
        if msg is None or not isinstance(msg.get("node_id"), str):
            continue

        # don't respond to the node's own broadcast
        if msg["node_id"] == node.node_id:
            continue

        logging.info("RECEIVED %s:%s %s", addr[0], addr[1], msg["type"])
        msg_type = msg["type"]

        # another node asking for peers?
        if msg_type == protocol.PEER_REQUEST:
            
            # create ack and broadcast it
            ack = protocol.make_peer_ack(node.node_id, msg["node_id"], node.tcp_port)
            broadcast(node, ack)

        # another node sending peer ack to addressed to current node?
        elif (msg_type == protocol.PEER_ACK and msg.get("to_node_id") == node.node_id 
              and isinstance(msg.get("node_id"), str)):
            try:
                tcp_port = int(msg["tcp_port"])
            
            except (KeyError, TypeError, ValueError):
                logging.info("Ignoring malformed PEER_ACK from %s:%s", addr[0], addr[1])
                continue

            # start tcp connection
            connections.connect_to_peer(node, addr[0], tcp_port, msg["node_id"])

        
def start_discovery(node):
    """Create the socket, start the listener thread, then announce ourselves."""
    node.udp_sock = create_udp_socket()
    threading.Thread(target=udp_listener_loop, args=(node,), daemon=True).start()
    send_peer_request(node)
