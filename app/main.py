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
        for i in range(0, len(peers_bytes), 6):
            ip = ".".join(str(b) for b in peers_bytes[i:i+4])
            port = struct.unpack("!H", peers_bytes[i+4:i+6])[0]
            print(f"{ip}:{port}")
    elif command == "handshake":
        torrent_path = sys.argv[2]
        peer_addr = sys.argv[3]
        peer_ip, peer_port = peer_addr.rsplit(":", 1)
        with open(torrent_path, "rb") as f:
            torrent = decode_bencode(f.read())
        info_hash = hashlib.sha1(bencode(torrent['info'])).digest()
        peer_id = b"00112233445566778899"
        handshake = (
            b"\x13BitTorrent protocol"
            + b"\x00" * 8
            + info_hash
            + peer_id
        )
        with socket.create_connection((peer_ip, int(peer_port))) as sock:
            sock.sendall(handshake)
            response = b""
            while len(response) < 68:
                response += sock.recv(68 - len(response))
        received_peer_id = response[48:68]
        print(f"Peer ID: {received_peer_id.hex()}")
    else:
        raise NotImplementedError(f"Unknown command {command}")


if __name__ == "__main__":
    main()
