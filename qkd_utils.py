# qkd_utils.py
import json, hashlib, base64

def send_json(sock, obj):
    """Send a JSON object followed by a newline (simple framing)."""
    data = (json.dumps(obj) + "\n").encode()
    sock.sendall(data)

def recv_json(sock):
    """Receive one JSON object (newline terminated)."""
    buffer = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            # connection closed
            break
        buffer += chunk
        if b"\n" in buffer:
            line, rest = buffer.split(b"\n", 1)
            # note: rest is discarded (we assume one message at a time)
            return json.loads(line.decode())
    if buffer:
        return json.loads(buffer.decode())
    return None

def derive_fernet_key_from_bits(bits_list):
    """Derive a Fernet-compatible 32-byte base64 key from a list of bits (['0','1',...])."""
    s = "".join(bits_list)
    digest = hashlib.sha256(s.encode()).digest()  # 32 bytes
    return base64.urlsafe_b64encode(digest)  # Fernet expects 32 url-safe base64 bytes
