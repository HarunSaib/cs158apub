"""
protocol.py
-----------
Everything about the wire format lives here, and nowhere else.
Other modules only call make_*(), send_message(), recv_message(),
encode_udp() and decode_udp(). They never touch raw bytes.

Wire format (see README.md for the full spec):

  UDP (discovery): one JSON object per datagram, UTF-8.
                   UDP keeps datagram boundaries, so no framing is needed.

  TCP (everything else):
      +---------------------+------------------------------+
      | 4-byte length N     | N bytes of UTF-8 JSON        |
      | (unsigned, big-end) | {"type": ..., "node_id": ...}|
      +---------------------+------------------------------+

  Every message has a "type" field (self-identifying) and a "node_id" field
  (the sender's UUID). File bytes are base64-encoded in the "content" field.
"""

import base64
import json
import struct

# ---------------------------------------------------------------- constants
UDP_PORT = 54321            # fixed by the assignment, used by every node
BROADCAST_ADDR = "<broadcast>"
BUFFER_SIZE = 4096
LENGTH_PREFIX = struct.Struct("!I")    # 4-byte unsigned int, network byte order

# The five message types
PEER_REQUEST = "PEER_REQUEST"
PEER_ACK = "PEER_ACK"
FILE_LIST = "FILE_LIST"
DATA_REQUEST = "DATA_REQUEST"
FILE_DATA = "FILE_DATA"

# Values for FILE_DATA["status"]
STATUS_OK = "OK"
STATUS_ERROR = "ERROR"


# ---------------------------------------------------------- message builders
# Each builder returns a plain dict. Keep the field names identical to the
# README spec; the other modules depend on them.

def make_peer_request(node_id):
    """UDP broadcast sent on startup: 'is anyone out there?'"""
    return {"type": PEER_REQUEST, "node_id": node_id}


def make_peer_ack(node_id, to_node_id, tcp_port):
    """UDP reply to a PEER_REQUEST.

    to_node_id : node_id of the requester, so other nodes can ignore this ACK
    tcp_port   : port this node's TCP server listens on
    The requester takes the IP address from recvfrom(), not from the message.
    """
    # TODO: return a dict with type, node_id, to_node_id, tcp_port
    raise NotImplementedError


def make_file_list(node_id, filenames):
    """TCP: the filenames currently in my shared/ directory (names only)."""
    # TODO
    raise NotImplementedError


def make_data_request(node_id, filename):
    """TCP: ask a peer for one file from its advertised list."""
    # TODO
    raise NotImplementedError


def make_file_data(node_id, filename, content):
    """TCP: successful response. content is raw bytes and gets base64-encoded here."""
    # TODO: status=STATUS_OK, content=encode_content(content)
    raise NotImplementedError


def make_file_error(node_id, filename, reason):
    """TCP: error response (file no longer exists). Same type as file data,
    distinguished by status=STATUS_ERROR, so the requester never waits forever."""
    # TODO: status=STATUS_ERROR, error=reason, no content
    raise NotImplementedError


def encode_content(data):
    """bytes -> base64 str (JSON can't hold raw bytes)."""
    return base64.b64encode(data).decode("ascii")


def decode_content(text):
    """base64 str -> bytes."""
    return base64.b64decode(text)


# ----------------------------------------------------------------------- UDP
def encode_udp(msg):
    """dict -> bytes for sendto()."""
    # TODO: json.dumps + encode
    raise NotImplementedError


def decode_udp(data):
    """bytes from recvfrom() -> dict, or None if it isn't valid JSON for our protocol
    (other programs on the LAN might also broadcast on this port)."""
    # TODO: try json.loads; return None on error or if "type" is missing
    raise NotImplementedError


# ----------------------------------------------------------------------- TCP
def send_message(sock, msg, send_lock):
    """Frame msg with a 4-byte length prefix and send it all.

    send_lock MUST be held while sending. Several threads (the file-list timer
    and the receive loop that serves files) write to the same socket, and
    interleaved bytes would corrupt the framing.
    Raises OSError if the socket is dead; the caller handles disconnects.
    """
    # TODO:
    #   body = json.dumps(msg).encode("utf-8")
    #   with send_lock: sock.sendall(LENGTH_PREFIX.pack(len(body)) + body)
    raise NotImplementedError


def recv_exact(sock, n):
    """Read exactly n bytes. Return None if the peer closed (recv returned b'').

    A short read does NOT mean the peer left. Keep looping until n bytes arrive.
    """
    # TODO: loop on sock.recv(min(BUFFER_SIZE, remaining)); collect chunks
    raise NotImplementedError


def recv_message(sock):
    """Read one complete framed message and return it as a dict.

    Returns None on a clean close or a mid-message close.
    Lets ConnectionResetError / OSError propagate; the receive loop treats them as a disconnect.
    """
    # TODO:
    #   header = recv_exact(sock, LENGTH_PREFIX.size); None -> return None
    #   (length,) = LENGTH_PREFIX.unpack(header)
    #   body = recv_exact(sock, length); None -> return None
    #   return json.loads(body.decode("utf-8"))
    raise NotImplementedError
