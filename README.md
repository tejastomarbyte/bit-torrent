# BitTorrent Client

A fully functional BitTorrent client built from scratch in Python. Supports downloading files via `.torrent` files and magnet links, implementing the core BitTorrent protocol and extensions.

## Features

- **Bencode** — custom parser and serializer for the bencode format used throughout the protocol
- **Torrent file parsing** — extracts tracker URL, file length, piece length, and piece hashes from `.torrent` files
- **HTTP tracker** — contacts trackers to discover peers using the compact peer format
- **Peer handshake** — establishes TCP connections with peers and performs the BitTorrent handshake
- **Piece downloading** — downloads individual pieces as 16 KiB blocks, with SHA-1 integrity verification
- **Full file download** — downloads and assembles all pieces into the complete file
- **Magnet link support** — parses magnet links and bootstraps torrent metadata directly from peers using the `ut_metadata` extension (BEP 9 / BEP 10)

## Usage

```sh
# Decode a bencoded value
./your_program.sh decode <bencoded_value>

# Print info from a torrent file
./your_program.sh info <torrent_file>

# List peers for a torrent
./your_program.sh peers <torrent_file>

# Perform a handshake with a peer
./your_program.sh handshake <torrent_file> <peer_ip>:<peer_port>

# Download a single piece
./your_program.sh download_piece -o <output_path> <torrent_file> <piece_index>

# Download the full file
./your_program.sh download -o <output_path> <torrent_file>

# Parse a magnet link
./your_program.sh magnet_parse <magnet_link>

# Handshake via magnet link (with extension protocol)
./your_program.sh magnet_handshake <magnet_link>

# Print info from a magnet link
./your_program.sh magnet_info <magnet_link>

# Download a single piece via magnet link
./your_program.sh magnet_download_piece -o <output_path> <magnet_link> <piece_index>

# Download the full file via magnet link
./your_program.sh magnet_download -o <output_path> <magnet_link>
```

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)

```sh
uv run app/main.py
```

## Implementation Details

- Bencode decoder handles strings, integers, lists, and nested dictionaries
- Piece integrity is verified using SHA-1 hashes before writing to disk
- Extension protocol (BEP 10) support — negotiates `ut_metadata` extension ID per peer and fetches the info dictionary directly from peers when using magnet links
- All TCP reads use length-prefixed framing with accumulation loops to handle partial reads
