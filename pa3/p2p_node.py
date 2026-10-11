"""
p2p_node.py  --  entry point
----------------------------
Usage:
    python p2p_node.py --port 6001                  # uses ./shared, ./downloads, ./log.txt
    python p2p_node.py --port 6002 --dir node2      # 2nd node on the same machine

Threads started (assignment minimum):
    UDP listener          (discovery.py)
    TCP accept loop       (connections.py)
    one receive loop/peer (connections.py)
    file-list timer       (file_manager.py)
    + the main thread runs the CLI below
"""

import argparse
import cmd
import os
import uuid

import connections
import discovery
import file_manager
import logger
from peer_table import PeerTable


class Node:
    """Shared state passed to every module. The modules stay plain functions."""

    def __init__(self, tcp_port: int, base_dir: str):
        self.node_id = str(uuid.uuid4())       # identifies us; used to ignore own broadcasts
        self.tcp_port = tcp_port
        self.shared_dir = os.path.join(base_dir, "shared")
        os.makedirs(self.shared_dir, exist_ok=True)
        self.downloads_dir = os.path.join(base_dir, "downloads")
        os.makedirs(self.downloads_dir, exist_ok=True)
        self.receiving_files = {}               # mapping filenames of files we are *actively* receiving to open writeable file objects.
        self.log_path = os.path.join(base_dir, "log.txt")
        self.peers = PeerTable()
        self.udp_sock = None                    # set by discovery.start_discovery


class P2PNodeCLI(cmd.Cmd):
    intro = "P2P node ready. Type 'help' for commands."
    prompt = '> '

    def __init__(self, node):
        super().__init__()
        self.node = node

    def emptyline(self):
        """Do nothing on an empty line (cmd.Cmd's default repeats the last command)."""
        pass

    def do_quit(self, _arg):
        """quit -- close all connections and exit"""
        return True

    def do_EOF(self, _arg):
        """Ctrl+D / Ctrl+Z -- same as quit"""
        print()                                 # ends the "> " prompt line before shutdown output
        return True

    def do_rebroadcast(self, _arg):
        """rebroadcast -- retransmit the advertising packet (this is done automatically on startup, but you may do it again)"""
        discovery.send_peer_request(self.node)

    def do_peers(self, _arg):
        """peers -- show connected peers and the files they advertise"""
        table = self.node.peers.snapshot()
        if not table:
            print("no connected peers")
            return
        for key, files in table.items():
            print(f"{key}:")
            for name in files:
                print(f"    {name}")
            if not files:
                print("    (no files)")

    def do_get(self, arg):
        """get <peer_key> <file> -- download a file (peer_key as shown by 'peers', e.g. 192.168.1.5:6001)"""
        parts = arg.split(maxsplit=1)
        if len(parts) != 2:
            print("usage: get <peer_key> <file>")
            return
        peer_key, filename = parts
        print(file_manager.request_file(self.node, peer_key, filename))

def main():
    parser = argparse.ArgumentParser(description="P2P file sharing agent")
    parser.add_argument("--port", type=int, required=True, help="TCP port to listen on")
    parser.add_argument("--dir", default=".", help="folder holding shared/, downloads/, log.txt")
    args = parser.parse_args()

    node = Node(args.port, args.dir)
    os.makedirs(node.shared_dir, exist_ok=True)
    os.makedirs(node.downloads_dir, exist_ok=True)
    logger.init_log(node.log_path)
    logger.log_info(f"Node {node.node_id} starting on TCP port {node.tcp_port}")

    # Order matters: the TCP server must be listening BEFORE we broadcast,
    # otherwise peers that ACK quickly would fail to connect.
    connections.start_tcp_server(node)
    file_manager.start_file_list_broadcaster(node)
    discovery.start_discovery(node)

    try:
        P2PNodeCLI(node).cmdloop()
    except KeyboardInterrupt:      # Ctrl+C: fall through to the normal shutdown below
        print()                    # move past the "> " prompt

    # Termination: no goodbye message. Close the sockets; peers see recv() == b''.
    for peer in node.peers.all_peers():
        peer.sock.close()
    logger.log_info("Node exiting")


if __name__ == "__main__":
    main()
