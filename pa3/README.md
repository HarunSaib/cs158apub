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
python p2p_node.py --port 6002 --dir demo
ode2
python p2p_node.py --port 6003 --dir demo
ode3
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
| `FILE_END` | TCP | `filename`, `status:"OK"` | `{"type":"FILE_END","node_id":"b2..","filename":"a.txt","status":"OK"}` |

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
[2026-10-11 17:33:59.195] PEER ADDED 10.0.0.240:6001 node=e34f3434-4347-47dd-aa7e-29d0e5d171d1
[2026-10-11 17:33:59.196] SENT 10.0.0.240:6001 FILE_LIST
[2026-10-11 17:33:59.196] RECEIVED 10.0.0.240:54321 PEER_ACK
[2026-10-11 17:33:59.196] RECEIVED 10.0.0.240:6001 FILE_LIST
[2026-10-11 17:35:02.114] PEER REMOVED 10.0.0.240:6004 node=44763556-7dfe-4bda-8fc7-87ef87e60a1b
```

`SENT`/`RECEIVED` lines give the peer address and message type; UDP broadcasts show `<broadcast>:54321`. On the accepting side the peer key uses the caller's ephemeral port and `node=None` until its first `FILE_LIST` arrives.

## Division of Work

| Member | Work |
|---|---|
| Harun Saib | Project skeleton and module layout; `peer_table.py`; `connections.py` (accept/connect, receive loop, disconnect handling); fixes to the file manager; CLI `peers`/`get`; README; demo and testing |
| Sean Worley | `cmd`-based CLI loop; first draft of `file_manager.py` (chunked transfer with `FILE_END`, `.part` downloads, serving/receiving files) |
| Aminah | `protocol.py` (message builders, UDP encoding, length-prefix framing, incl. the `recv_message` return fix); `discovery.py` (broadcast, listener, `PEER_ACK` handling); switch to Python `logging` |

## Execution Example

Five nodes on one machine (`10.0.0.240`), started ~3 s apart with the commands under *How to Run* (`--port 6001` … `--port 6005 --dir demo
ode5`). Excerpts from the demo's `log.txt` files; `...` marks omitted lines. Node IDs: node 1 `e2f188fa…`, node 3 `a211b8ec…`, node 5 `c8bd01b0…`.

**Discovery and file lists.** Node 5 starts last, broadcasts a `PEER_REQUEST`, gets an ACK from each running node, and connects to all four; each connection exchanges `FILE_LIST` immediately:

```
[2026-10-11 21:30:44.503] Node c8bd01b0-faa0-4c38-b13e-f70ea2aa5e94 starting on TCP port 6005
[2026-10-11 21:30:44.505] SENT <broadcast>:54321 PEER_REQUEST
[2026-10-11 21:30:44.505] RECEIVED 10.0.0.240:54321 PEER_ACK
[2026-10-11 21:30:44.511] PEER ADDED 10.0.0.240:6001 node=e2f188fa-1240-44ff-97e6-2120550678a9
[2026-10-11 21:30:44.511] SENT 10.0.0.240:6001 FILE_LIST
[2026-10-11 21:30:44.511] RECEIVED 10.0.0.240:6001 FILE_LIST
...
[2026-10-11 21:30:44.512] PEER ADDED 10.0.0.240:6002 node=f09d78ab-43f3-4e9f-a829-e193f3294b9a
...
[2026-10-11 21:30:44.513] PEER ADDED 10.0.0.240:6003 node=a211b8ec-9d00-444d-b276-f9ea4e6d61b5
...
[2026-10-11 21:30:44.515] PEER ADDED 10.0.0.240:6004 node=ff8f3782-230d-49b8-81ac-4ba4f3c18dd8
...
[2026-10-11 21:30:54.573] received updated file list from 10.0.0.240:6002 (node ID f09d78ab-43f3-4e9f-a829-e193f3294b9a)
[2026-10-11 21:30:58.046] received updated file list from 10.0.0.240:6003 (node ID a211b8ec-9d00-444d-b276-f9ea4e6d61b5)
```

**Chunked file transfer.** On node 5: `get 10.0.0.240:6001 wallpaper.jpg` (1,602,752 bytes = 196 chunks of up to 8192 bytes).

Node 5 (requester):
```
[2026-10-11 21:31:00.493] SENT 10.0.0.240:6001 DATA_REQUEST
[2026-10-11 21:31:00.494] RECEIVED 10.0.0.240:6001 FILE_DATA
[2026-10-11 21:31:00.494] received 8192 bytes for file wallpaper.jpg
[2026-10-11 21:31:00.495] RECEIVED 10.0.0.240:6001 FILE_DATA
[2026-10-11 21:31:00.495] received 8192 bytes for file wallpaper.jpg
...                                   (196 chunks in total)
[2026-10-11 21:31:00.549] RECEIVED 10.0.0.240:6001 FILE_DATA
[2026-10-11 21:31:00.549] received 5312 bytes for file wallpaper.jpg
[2026-10-11 21:31:00.549] RECEIVED 10.0.0.240:6001 FILE_END
[2026-10-11 21:31:00.560] download complete: wallpaper.jpg
```

Node 1 (server; node 5 appears under its ephemeral port 54261):
```
[2026-10-11 21:31:00.493] RECEIVED 10.0.0.240:54261 DATA_REQUEST
[2026-10-11 21:31:00.494] SENT 10.0.0.240:54261 FILE_DATA
[2026-10-11 21:31:00.494] SENT 10.0.0.240:54261 FILE_DATA
...
[2026-10-11 21:31:00.545] SENT 10.0.0.240:54261 FILE_DATA
[2026-10-11 21:31:00.545] SENT 10.0.0.240:54261 FILE_END
```

The copies in node 5's `downloads/` and `shared/` match the original (SHA-256 `a37491a5e479e191…` for all three). From then on node 5 advertises `wallpaper.jpg` in its `FILE_LIST`.

**A node leaving.** Node 3 runs `quit`. Every other node detects the closed socket within a millisecond and drops node 3 and its files:

```
node 1: [2026-10-11 21:31:34.349] PEER REMOVED 10.0.0.240:54256 node=a211b8ec-9d00-444d-b276-f9ea4e6d61b5
node 2: [2026-10-11 21:31:34.349] PEER REMOVED 10.0.0.240:54257 node=a211b8ec-9d00-444d-b276-f9ea4e6d61b5
node 4: [2026-10-11 21:31:34.350] PEER REMOVED 10.0.0.240:6003 node=a211b8ec-9d00-444d-b276-f9ea4e6d61b5
node 5: [2026-10-11 21:31:34.350] PEER REMOVED 10.0.0.240:6003 node=a211b8ec-9d00-444d-b276-f9ea4e6d61b5
```

The remaining nodes keep exchanging `FILE_LIST`s with each other, now without node 3.
