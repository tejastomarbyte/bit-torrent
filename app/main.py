import hashlib
import json
import socket
import struct
import sys
import urllib.parse
import urllib.request

# import bencodepy - available if you need it!
# import requests - available if you need it!

# Examples:
#
# - decode_bencode(b"5:hello") -> b"hello"
# - decode_bencode(b"10:hello12345") -> b"hello12345"
def bencode(value):
    if isinstance(value, bytes):
        return str(len(value)).encode() + b":" + value
    elif isinstance(value, int):
        return b"i" + str(value).encode() + b"e"
    elif isinstance(value, list):
        return b"l" + b"".join(bencode(i) for i in value) + b"e"
    elif isinstance(value, dict):
        encoded = b"d"
        for k in sorted(value.keys()):
            encoded += bencode(k.encode() if isinstance(k, str) else k)
            encoded += bencode(value[k])
        return encoded + b"e"
    raise TypeError(f"Unsupported type: {type(value)}")


def decode_bencode(bencoded_value):
    value, _ = _decode(bencoded_value)
    return value


def _decode(data):
    if chr(data[0]).isdigit():
        colon = data.find(b":")
        if colon == -1:
            raise ValueError("Invalid encoded string")
        length = int(data[:colon])
        start = colon + 1
        return data[start:start + length], start + length
    elif data[0:1] == b"i":
        end = data.find(b"e")
        if end == -1:
            raise ValueError("Invalid encoded integer")
        return int(data[1:end]), end + 1
    elif data[0:1] == b"l":
        items = []
        pos = 1
        while data[pos:pos+1] != b"e":
            item, consumed = _decode(data[pos:])
            items.append(item)
            pos += consumed
        return items, pos + 1
    elif data[0:1] == b"d":
        result = {}
        pos = 1
        while data[pos:pos+1] != b"e":
            key, consumed = _decode(data[pos:])
            pos += consumed
            value, consumed = _decode(data[pos:])
            pos += consumed
            result[key.decode()] = value
        return result, pos + 1
    else:
        raise NotImplementedError("Unsupported bencode type")


BLOCK_SIZE = 16 * 1024


def recv_all(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Peer closed connection")
        data += chunk
    return data


def recv_msg(sock):
    length = struct.unpack("!I", recv_all(sock, 4))[0]
    if length == 0:
        return None, b""  # keep-alive
    msg_id = struct.unpack("!B", recv_all(sock, 1))[0]
    payload = recv_all(sock, length - 1)
    return msg_id, payload


def send_msg(sock, msg_id, payload=b""):
    sock.sendall(struct.pack("!IB", 1 + len(payload), msg_id) + payload)


EXTENSION_RESERVED = b"\x00\x00\x00\x00\x00\x10\x00\x00"


def do_handshake(sock, info_hash, reserved=b"\x00" * 8):
    peer_id = b"00112233445566778899"
    sock.sendall(b"\x13BitTorrent protocol" + reserved + info_hash + peer_id)
    return recv_all(sock, 68)


def parse_magnet(magnet):
    qs = urllib.parse.urlparse(magnet).query
    params = urllib.parse.parse_qs(qs)
    info_hash_hex = params["xt"][0].removeprefix("urn:btih:")
    info_hash = bytes.fromhex(info_hash_hex)
    tracker_url = urllib.parse.unquote(params["tr"][0])
    return info_hash, info_hash_hex, tracker_url


def get_peers_from_magnet(info_hash, tracker_url):
    params = urllib.parse.urlencode({
        "info_hash": info_hash,
        "peer_id": "00112233445566778899",
        "port": 6881,
        "uploaded": 0,
        "downloaded": 0,
        "left": 999,
        "compact": 1,
    })
    url = tracker_url + "?" + params
    with urllib.request.urlopen(url) as resp:
        response = decode_bencode(resp.read())
    peers_bytes = response['peers']
    peers = []
    for i in range(0, len(peers_bytes), 6):
        ip = ".".join(str(b) for b in peers_bytes[i:i+4])
        port = struct.unpack("!H", peers_bytes[i+4:i+6])[0]
        peers.append((ip, port))
    return peers


def download_piece_from_sock(sock, piece_index, piece_length, total_length, pieces):
    actual_length = min(piece_length, total_length - piece_index * piece_length)
    offset = 0
    while offset < actual_length:
        block_len = min(BLOCK_SIZE, actual_length - offset)
        send_msg(sock, 6, struct.pack("!III", piece_index, offset, block_len))
        offset += block_len
    piece_data = bytearray(actual_length)
    received = 0
    while received < actual_length:
        msg_id, payload = recv_msg(sock)
        if msg_id != 7:
            continue
        begin = struct.unpack("!II", payload[:8])[1]
        block = payload[8:]
        piece_data[begin:begin + len(block)] = block
        received += len(block)
    expected_hash = pieces[piece_index * 20:(piece_index + 1) * 20]
    assert hashlib.sha1(piece_data).digest() == expected_hash, f"Hash mismatch for piece {piece_index}"
    return bytes(piece_data)


def get_peers(torrent):
    info = torrent['info']
    info_hash = hashlib.sha1(bencode(info)).digest()
    params = urllib.parse.urlencode({
        "info_hash": info_hash,
        "peer_id": "00112233445566778899",
        "port": 6881,
        "uploaded": 0,
        "downloaded": 0,
        "left": info['length'],
        "compact": 1,
    })
    url = torrent['announce'].decode() + "?" + params
    with urllib.request.urlopen(url) as resp:
        response = decode_bencode(resp.read())
    peers_bytes = response['peers']
    peers = []
    for i in range(0, len(peers_bytes), 6):
        ip = ".".join(str(b) for b in peers_bytes[i:i+4])
        port = struct.unpack("!H", peers_bytes[i+4:i+6])[0]
        peers.append((ip, port))
    return peers


def main():
    command = sys.argv[1]

    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!", file=sys.stderr)

    if command == "decode":
        bencoded_value = sys.argv[2].encode()

        def bytes_to_str(data):
            if isinstance(data, bytes):
                return data.decode()
            raise TypeError(f"Type not serializable: {type(data)}")

        print(json.dumps(decode_bencode(bencoded_value), default=bytes_to_str))
    elif command == "info":
        torrent_path = sys.argv[2]
        with open(torrent_path, "rb") as f:
            torrent = decode_bencode(f.read())
        info = torrent['info']
        info_hash = hashlib.sha1(bencode(info)).hexdigest()
        print(f"Tracker URL: {torrent['announce'].decode()}")
        print(f"Length: {info['length']}")
        print(f"Info Hash: {info_hash}")
        print(f"Piece Length: {info['piece length']}")
        print("Piece Hashes:")
        pieces = info['pieces']
        for i in range(0, len(pieces), 20):
            print(pieces[i:i+20].hex())
    elif command == "peers":
        torrent_path = sys.argv[2]
        with open(torrent_path, "rb") as f:
            torrent = decode_bencode(f.read())
        for ip, port in get_peers(torrent):
            print(f"{ip}:{port}")
    elif command == "handshake":
        torrent_path = sys.argv[2]
        peer_ip, peer_port = sys.argv[3].rsplit(":", 1)
        with open(torrent_path, "rb") as f:
            torrent = decode_bencode(f.read())
        info_hash = hashlib.sha1(bencode(torrent['info'])).digest()
        with socket.create_connection((peer_ip, int(peer_port))) as sock:
            resp = do_handshake(sock, info_hash)
        print(f"Peer ID: {resp[48:68].hex()}")
    elif command == "download_piece":
        output_path = sys.argv[3]
        torrent_path = sys.argv[4]
        piece_index = int(sys.argv[5])
        with open(torrent_path, "rb") as f:
            torrent = decode_bencode(f.read())
        info = torrent['info']
        info_hash = hashlib.sha1(bencode(info)).digest()
        peer_ip, peer_port = get_peers(torrent)[0]
        with socket.create_connection((peer_ip, peer_port)) as sock:
            do_handshake(sock, info_hash)
            while True:
                msg_id, _ = recv_msg(sock)
                if msg_id == 5:
                    break
            send_msg(sock, 2)
            while True:
                msg_id, _ = recv_msg(sock)
                if msg_id == 1:
                    break
            piece_data = download_piece_from_sock(sock, piece_index, info['piece length'], info['length'], info['pieces'])
        with open(output_path, "wb") as f:
            f.write(piece_data)
        print(f"Piece {piece_index} downloaded to {output_path}.")
    elif command == "download":
        output_path = sys.argv[3]
        torrent_path = sys.argv[4]
        with open(torrent_path, "rb") as f:
            torrent = decode_bencode(f.read())
        info = torrent['info']
        info_hash = hashlib.sha1(bencode(info)).digest()
        piece_length = info['piece length']
        total_length = info['length']
        pieces = info['pieces']
        num_pieces = len(pieces) // 20

        peer_ip, peer_port = get_peers(torrent)[0]
        with socket.create_connection((peer_ip, peer_port)) as sock:
            do_handshake(sock, info_hash)
            while True:
                msg_id, _ = recv_msg(sock)
                if msg_id == 5:
                    break
            send_msg(sock, 2)
            while True:
                msg_id, _ = recv_msg(sock)
                if msg_id == 1:
                    break
            all_pieces = []
            for i in range(num_pieces):
                piece_data = download_piece_from_sock(sock, i, piece_length, total_length, pieces)
                all_pieces.append(piece_data)

        with open(output_path, "wb") as f:
            for piece_data in all_pieces:
                f.write(piece_data)
        print(f"Downloaded {torrent_path} to {output_path}.")
    elif command == "magnet_handshake":
        magnet = sys.argv[2]
        info_hash, _, tracker_url = parse_magnet(magnet)
        peer_ip, peer_port = get_peers_from_magnet(info_hash, tracker_url)[0]
        with socket.create_connection((peer_ip, peer_port)) as sock:
            resp = do_handshake(sock, info_hash, reserved=EXTENSION_RESERVED)
        print(f"Peer ID: {resp[48:68].hex()}")
    elif command == "magnet_parse":
        magnet = sys.argv[2]
        qs = urllib.parse.urlparse(magnet).query
        params = urllib.parse.parse_qs(qs)
        info_hash = params["xt"][0].removeprefix("urn:btih:")
        tracker_url = urllib.parse.unquote(params["tr"][0])
        print(f"Tracker URL: {tracker_url}")
        print(f"Info Hash: {info_hash}")
    else:
        raise NotImplementedError(f"Unknown command {command}")


if __name__ == "__main__":
    main()
