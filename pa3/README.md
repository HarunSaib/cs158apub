# PA3 – P2P Data Sharing Agent

> The assignment says to use `pa2/`, but `pa2/` already holds the leader-election assignment, so this one lives in `pa3/`.

Every node is both a client and a server. Nodes find each other with UDP broadcast on port 54321, keep one TCP connection per peer, advertise their `shared/` files every 10 seconds, and serve files on request.

## How to Run

Requires Python 3.8+ and no extra packages.

```powershell
cd pa3
python p2p_node.py --port 6001                  # uses ./shared, ./downloads, ./log.txt
```

To run several nodes on one machine, give each node its own port and folder:

```powershell
python p2p_node.py --port 6002 --dir node2
python p2p_node.py --port 6003 --dir node3
```

CLI commands: `peers`, `get <peer_key> <file>`, `rebroadcast`, `quit` (or Ctrl+D / Ctrl+Z). `help` lists them.

## Files

| File | Purpose |
|---|---|
| `protocol.py` | message builders, length-prefix framing, UDP encode/decode |
| `discovery.py` | UDP PEER_REQUEST / PEER_ACK on port 54321 |
| `peer_table.py` | thread-safe peer → files table |
| `connections.py` | TCP accept/connect, per-peer receive loop, disconnect handling, logging of every TCP message |
| `file_manager.py` | file list timer, serving and saving files |
| `p2p_node.py` | `Node` state, logging setup (`log.txt` + console), startup order, CLI |

## Message Format Specification

All messages are JSON objects encoded as UTF-8. Every message carries:

| Field | Type | Meaning |
|---|---|---|
| `type` | string | one of the types below, so every message identifies itself |
| `node_id` | string (UUID4) | random ID the sender generated at startup |

### Transport and Message Boundaries

- **UDP (PEER_REQUEST, PEER_ACK):** one JSON object per datagram, sent to port 54321 (address `<broadcast>`). UDP keeps datagram boundaries, so no framing is needed.
- **TCP (FILE_LIST, DATA_REQUEST, FILE_DATA, FILE_END):** each message is framed as

  ```
  +--------------------------+-------------------------------+
  | length N: 4 bytes,       | N bytes: UTF-8 JSON object    |
  | unsigned, big-endian     |                               |
  +--------------------------+-------------------------------+
  ```

  The receiver reads exactly 4 bytes, decodes N, then reads exactly N bytes, looping on `recv` in both steps. If `recv` returns empty at any point, or raises `ConnectionResetError`, the peer has disconnected.

### Message Types

| Type | Transport | Fields (besides `type`, `node_id`) | Example |
|---|---|---|---|
| `PEER_REQUEST` | UDP broadcast | none | `{"type":"PEER_REQUEST","node_id":"a1.."}` |
| `PEER_ACK` | UDP broadcast | `to_node_id` (the requester), `tcp_port` (int) | `{"type":"PEER_ACK","node_id":"b2..","to_node_id":"a1..","tcp_port":6002}` |
| `FILE_LIST` | TCP | `files`: list of filenames | `{"type":"FILE_LIST","node_id":"b2..","files":["a.txt","cat.jpg"]}` |
| `DATA_REQUEST` | TCP | `filename` | `{"type":"DATA_REQUEST","node_id":"a1..","filename":"a.txt"}` |
| `FILE_DATA` (chunk) | TCP | `filename`, `status:"OK"`, `content` (base64 of up to 8192 bytes) | `{"type":"FILE_DATA",...,"status":"OK","content":"aGVsbG8gd29ybGQ="}` |
| `FILE_DATA` (error) | TCP | `filename`, `status:"ERROR"`, `error` (text) | `{"type":"FILE_DATA",...,"status":"ERROR","error":"File not found"}` |
| `FILE_END` | TCP | `filename` | `{"type":"FILE_END","node_id":"b2..","filename":"a.txt"}` |

`FILE_END` is a sixth type, beyond the five required, that marks the end of a chunked file.

**Peer IP address.** A PEER_ACK does not contain an IP address. The requester takes it from the source address that `recvfrom()` returns.

**Why PEER_ACK is broadcast.** When several nodes on one machine all bind UDP 54321, a unicast datagram reaches only one of those sockets, and it may not be the requester's. A broadcast reaches every node. Nodes ignore any ACK whose `to_node_id` is not their own ID, and they ignore their own broadcasts by checking `node_id`.

**Errors.** If the requested file is missing, the server sends `FILE_DATA` with `status:"ERROR"` and keeps the connection open. The requester never has to wait forever.

### File Content Encoding and Chunking

A file is sent as `FILE_DATA` messages carrying up to 8192 bytes each, **base64-encoded** in `content`, followed by one `FILE_END`. A 0-byte file is just a `FILE_END`.

- **Why base64:** every TCP message stays one JSON object behind the same length prefix, so there is a single parser. The ~33% overhead is acceptable here.
- **Why chunks:** neither side holds a whole file in memory, and file lists can be sent between chunks.
- **Errors mid-transfer:** the server sends an error `FILE_DATA` instead of `FILE_END`. The requester renames its partial file to `<name>.corrupted` and does not share it.

## Connection Rules

1. On startup, a node starts its TCP server and then broadcasts `PEER_REQUEST`.
2. Every node that receives the request broadcasts a `PEER_ACK`.
3. The **requester is the TCP client**: it connects to `(source IP of ACK, tcp_port)`. It does not connect if it already has a connection to that `node_id`.
4. Both sides send `FILE_LIST` immediately, then every 10 seconds.
5. Chunks are written to `downloads/<name>.part`. On `FILE_END` the file is renamed to `downloads/<name>` and only then copied into `shared/`, so a half-written file is never advertised.
6. A node never requests a file it already has in `shared/`. Files are identified by name, so the existing copy wins.
7. Each `FILE_LIST` replaces that peer's previous list in the peer table.
8. On an error reply, the requester logs it and stops tracking that download. It does not retry.
9. Each `DATA_REQUEST` is served on its own thread, so a node keeps reading from a peer while sending it a file (two nodes sending each other large files can't block each other).
10. A node leaves by closing its sockets. Peers detect this when `recv` returns empty or raises, then remove the peer and its files from their table.

### Logging

Each node writes `log.txt` (and the console) with a millisecond timestamp per line, e.g.:

```
[2026-10-11 17:02:53.161] PEER ADDED 10.0.0.240:52488 node=None
[2026-10-11 17:02:53.161] SENT 10.0.0.240:52488 FILE_LIST
[2026-10-11 17:02:53.161] RECEIVED 10.0.0.240:52488 FILE_LIST
[2026-10-11 17:03:10.598] PEER REMOVED 10.0.0.240:6101 node=aebd96fc-...
```

`SENT`/`RECEIVED` lines give the peer address and message type; UDP broadcasts show `<broadcast>:54321`. On the accepting side the peer key uses the caller's ephemeral port and `node=None` until its first `FILE_LIST` arrives.

### Known Limitations

- Each file is identified by name only; a file is not re-downloaded if one with the same name is already in `shared/`.
- If a peer disconnects mid-transfer, that filename stays marked as downloading until the node restarts.
- If two nodes start at the same instant, each may dial the other and they end up with two connections. Start nodes at least a second apart.

## Division of Work

TODO: who wrote which files (must match the commit history).

## Execution Example

TODO: paste terminal output or screenshots from the 5-node demo showing discovery, file lists propagating, a file transfer, and a node leaving.
