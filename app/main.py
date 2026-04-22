import hashlib
import json
import sys

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
        info_hash = hashlib.sha1(bencode(torrent['info'])).hexdigest()
        print(f"Tracker URL: {torrent['announce'].decode()}")
        print(f"Length: {torrent['info']['length']}")
        print(f"Info Hash: {info_hash}")
    else:
        raise NotImplementedError(f"Unknown command {command}")


if __name__ == "__main__":
    main()
