def encode_uvarint(value: int) -> bytes:
    if value < 0:
        raise ValueError("value must be non-negative")
    out = bytearray()
    while True:
        to_write = value & 0x7F
        value >>= 7
        if value:
            out.append(to_write | 0x80)
        else:
            out.append(to_write)
            break
    return bytes(out)


def decode_uvarint_from_bytes(data: bytes, start: int = 0) -> tuple[int, int]:
    shift = 0
    result = 0
    pos = start
    while True:
        if pos >= len(data):
            raise ValueError("incomplete varint")
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result, pos
        shift += 7
        if shift > 63:
            raise ValueError("varint too long")


def read_uvarint(fileobj) -> int:
    shift = 0
    result = 0
    while True:
        b = fileobj.read(1)
        if not b:
            raise EOFError
        byte = b[0]
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            return result
        shift += 7
        if shift > 63:
            raise ValueError("varint too long")

