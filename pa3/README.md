# PA3 – P2P Data Sharing Agent

Located in `pa3/` because `pa2/` holds the earlier leader-election assignment.

Each node is both a client and a server. Nodes discover each other by UDP broadcast on port 54321, keep one TCP connection per peer, advertise their `shared/` files every 10 seconds, and serve files on request.

## How to Run

Python 3.8+, no extra packages.

```powershell
cd pa3
python p2p_node.py --port 6001                      # uses ./shared, ./downloads, ./log.txt
python p2p_node.py --port 6002 --dir demo/node2     # additional nodes: own port and folder
python p2p_node.py --port 6003 --dir demo/node3
```

| Option | Meaning |
|---|---|
| `--port` | TCP port this node listens on (required) |
| `--dir` | folder holding the node's `shared/`, `downloads/`, and `log.txt` (default `.`) |

| Command | Action |
|---|---|
| `peers` | list connected peers and their files |
| `get <peer_key> <file>` | download a file; `peer_key` as shown by `peers` |
| `rebroadcast` | send another `PEER_REQUEST` |
| `quit` / Ctrl+D / Ctrl+Z / Ctrl+C | close all connections and exit |
| `help` | list commands |

## Files

| File | Purpose |
|---|---|
| `protocol.py` | message builders, length-prefix framing, UDP encode/decode |
| `discovery.py` | UDP `PEER_REQUEST` / `PEER_ACK` on port 54321 |
| `peer_table.py` | thread-safe table of peers and their files |
| `connections.py` | TCP accept/connect, per-peer receive loop, disconnect handling |
| `file_manager.py` | file-list timer, serving and saving files |
| `p2p_node.py` | node state, logging setup, startup, CLI |

## Message Format Specification

All messages are UTF-8 JSON objects. Every message has these fields:

| Field | Type | Meaning |
|---|---|---|
| `type` | string | message type (see table below) |
| `node_id` | string (UUID4) | sender's ID, generated at startup |

### Message Boundaries

- **UDP** (`PEER_REQUEST`, `PEER_ACK`): one JSON object per datagram, sent to `<broadcast>:54321`. UDP preserves datagram boundaries, so no framing is added.
- **TCP** (`FILE_LIST`, `DATA_REQUEST`, `FILE_DATA`, `FILE_END`): TCP is a byte stream, so each message is length-prefixed:

  ```
  +--------------------------+-------------------------------+
  | length N: 4 bytes,       | N bytes: UTF-8 JSON object    |
  | unsigned, big-endian     |                               |
  +--------------------------+-------------------------------+
  ```

  The receiver reads exactly 4 bytes to get N, then exactly N bytes, looping on `recv` until each count is reached. The next byte starts the next message. An empty `recv` at any point, or `ConnectionResetError`, means the peer disconnected.

### Message Types

| Type | Transport | Fields (besides `type`, `node_id`) | Example |
|---|---|---|---|
| `PEER_REQUEST` | UDP broadcast | none | `{"type":"PEER_REQUEST","node_id":"a1.."}` |
| `PEER_ACK` | UDP broadcast | `to_node_id` (requester's ID), `tcp_port` (int) | `{"type":"PEER_ACK","node_id":"b2..","to_node_id":"a1..","tcp_port":6002}` |
| `FILE_LIST` | TCP | `files` (list of filenames) | `{"type":"FILE_LIST","node_id":"b2..","files":["a.txt","cat.jpg"]}` |
| `DATA_REQUEST` | TCP | `filename` | `{"type":"DATA_REQUEST","node_id":"a1..","filename":"a.txt"}` |
| `FILE_DATA` (chunk) | TCP | `filename`, `status:"OK"`, `content` (base64 of up to 8192 bytes) | `{"type":"FILE_DATA",...,"status":"OK","content":"aGVsbG8="}` |
| `FILE_DATA` (error) | TCP | `filename`, `status:"ERROR"`, `error` (text) | `{"type":"FILE_DATA",...,"status":"ERROR","error":"File not found"}` |
| `FILE_END` | TCP | `filename`, `status:"OK"` | `{"type":"FILE_END","node_id":"b2..","filename":"a.txt","status":"OK"}` |

- `PEER_ACK` carries no IP address; the requester uses the source address from `recvfrom()`.
- `PEER_ACK` is broadcast; nodes act only on ACKs whose `to_node_id` matches their own ID.
- Nodes ignore UDP messages carrying their own `node_id`.
- `FILE_END` is an additional sixth type marking the end of a file.

### File Content Encoding

- A file is sent as a sequence of `FILE_DATA` messages, each with up to 8192 bytes of the file base64-encoded in `content`, followed by one `FILE_END`.
- A 0-byte file is sent as a single `FILE_END`.
- A missing file is answered with an error `FILE_DATA`; the connection stays open.
- If reading fails mid-transfer, the server sends an error `FILE_DATA` instead of `FILE_END`; the requester renames its partial file to `<name>.corrupted`.

## Connection Rules

1. On startup a node starts its TCP server, then broadcasts `PEER_REQUEST`.
2. Every node receiving a `PEER_REQUEST` broadcasts a `PEER_ACK`.
3. The requester is the TCP client: it connects to the ACK's source IP and `tcp_port`, unless already connected to that `node_id`.
4. Both sides send `FILE_LIST` right after connecting, then every 10 seconds.
5. Each `FILE_LIST` replaces that peer's previous list in the peer table.
6. A node does not request a file already in its `shared/`.
7. Incoming chunks are written to `downloads/<name>.part`; on `FILE_END` the file is renamed to `downloads/<name>`, then copied into `shared/`.
8. On an error reply the requester logs it and stops tracking that download (no retry).
9. Each `DATA_REQUEST` is served on its own thread.
10. A node leaves by closing its sockets. Peers detect the close on `recv`, then remove the peer and its files.

## Logging

Each node writes `log.txt` and the console, one timestamped line per event:

| Line | Logged when |
|---|---|
| `SENT <addr> <type>` | any message sent (UDP broadcasts show `<broadcast>:54321`) |
| `RECEIVED <addr> <type>` | any message received |
| `PEER ADDED <addr> node=<id>` | after a successful TCP connection |
| `PEER REMOVED <addr> node=<id>` | after a detected disconnection |

On the accepting side, `<addr>` uses the caller's ephemeral port, and `node=None` until the caller's first `FILE_LIST`.

## Limitations

- Files are identified by name only.
- If a peer disconnects mid-transfer, that filename stays marked as downloading until restart.
- Two nodes started at the same instant may open two connections to each other; start nodes at least 1 s apart.

## Division of Work

| Member | Work |
|---|---|
| Harun Saib | project skeleton and module layout; `peer_table.py`; `connections.py` (accept/connect, receive loop, disconnect handling); file manager fixes; CLI `peers`/`get`; README; demo and testing |
| Sean Worley | `cmd`-based CLI loop; first draft of `file_manager.py` (chunked transfer with `FILE_END`, `.part` downloads, serving/receiving files) |
| Aminah | `protocol.py` (message builders, UDP encoding, length-prefix framing, `recv_message` fix); `discovery.py` (broadcast, listener, `PEER_ACK` handling); Python `logging` setup |

## Execution Example

Five nodes on one machine (`10.0.0.240`), ports 6001–6005, started ~3 s apart. Excerpts from the nodes' `log.txt`; `...` marks omitted lines. Node IDs: node 1 `e2f188fa…`, node 3 `a211b8ec…`, node 5 `c8bd01b0…`.

**Discovery and file lists** (node 5, started last):

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

**File transfer** — node 5 runs `get 10.0.0.240:6001 wallpaper.jpg` (1,602,752 bytes, 196 chunks).

Node 5 (requester):
```
[2026-10-11 21:31:00.493] SENT 10.0.0.240:6001 DATA_REQUEST
[2026-10-11 21:31:00.494] RECEIVED 10.0.0.240:6001 FILE_DATA
[2026-10-11 21:31:00.494] received 8192 bytes for file wallpaper.jpg
[2026-10-11 21:31:00.495] RECEIVED 10.0.0.240:6001 FILE_DATA
[2026-10-11 21:31:00.495] received 8192 bytes for file wallpaper.jpg
...
[2026-10-11 21:31:00.549] RECEIVED 10.0.0.240:6001 FILE_DATA
[2026-10-11 21:31:00.549] received 5312 bytes for file wallpaper.jpg
[2026-10-11 21:31:00.549] RECEIVED 10.0.0.240:6001 FILE_END
[2026-10-11 21:31:00.560] download complete: wallpaper.jpg
```

Node 1 (server):
```
[2026-10-11 21:31:00.493] RECEIVED 10.0.0.240:54261 DATA_REQUEST
[2026-10-11 21:31:00.494] SENT 10.0.0.240:54261 FILE_DATA
[2026-10-11 21:31:00.494] SENT 10.0.0.240:54261 FILE_DATA
...
[2026-10-11 21:31:00.545] SENT 10.0.0.240:54261 FILE_DATA
[2026-10-11 21:31:00.545] SENT 10.0.0.240:54261 FILE_END
```

SHA-256 of the original and of node 5's `downloads/` and `shared/` copies: `a37491a5e479e191…` (identical).

**Node leaving** — node 3 runs `quit`; the other four nodes remove it:

```
node 1: [2026-10-11 21:31:34.349] PEER REMOVED 10.0.0.240:54256 node=a211b8ec-9d00-444d-b276-f9ea4e6d61b5
node 2: [2026-10-11 21:31:34.349] PEER REMOVED 10.0.0.240:54257 node=a211b8ec-9d00-444d-b276-f9ea4e6d61b5
node 4: [2026-10-11 21:31:34.350] PEER REMOVED 10.0.0.240:6003 node=a211b8ec-9d00-444d-b276-f9ea4e6d61b5
node 5: [2026-10-11 21:31:34.350] PEER REMOVED 10.0.0.240:6003 node=a211b8ec-9d00-444d-b276-f9ea4e6d61b5
```
