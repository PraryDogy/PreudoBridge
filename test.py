import numpy as np
import imagecodecs

def lzw_encode(seq: bytes) -> bytes:
    CLEAR_TOKEN = 256
    END_TOKEN = 257
    # init table
    table = {bytes([i]): i for i in range(256)}
    table[object()] = CLEAR_TOKEN
    table[object()] = END_TOKEN
    assert len(table) == 258

    def gen_code():
        yield CLEAR_TOKEN
        s = b""
        for c in seq:
            c = bytes([c])
            sc = s + c
            if sc in table:
                s = sc
            else:
                yield table[s]
                table[sc] = len(table)
                s = c

        if s:
            yield table[s]
        yield END_TOKEN

    s = "".join(
        f"{code:0{len(table).bit_length()}b}"
        for code in gen_code()
    )
    x = int(s, 2)
    m = x.bit_length() % 8
    if m != 0:
        x <<= 8 - m

    return x.to_bytes(x.bit_length() // 8, 'big')



def test_lzw_encode():
    data = np.random.randint(0, 255, size=1000, dtype=np.uint8).tobytes()
    encoded = lzw_encode(data)
    assert imagecodecs.lzw_decode(encoded) == data
