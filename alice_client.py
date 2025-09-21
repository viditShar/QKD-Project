import socket, random
from qkd_utils import send_json, recv_json, derive_fernet_key_from_bits
from cryptography.fernet import Fernet
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--host", required=True)
parser.add_argument("--port", type=int, default=65432)
parser.add_argument("--num", type=int, default=16)
parser.add_argument("--message", default="Hello Bob, this is Alice!")
args = parser.parse_args()

def build_states(bits, bases):
    return [{"basis": b, "bit": int(bt)} for bt,b in zip(bits,bases)]

def main():
    host, port, n = args.host, args.port, args.num
    alice_bits = [random.randint(0,1) for _ in range(n)]
    alice_bases = [random.choice(['Z','X']) for _ in range(n)]
    states = build_states(alice_bits, alice_bases)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    print("Alice: connected to", host, port)

    send_json(s, {"type":"init", "num_qubits": n})
    msg = recv_json(s)
    if not msg or msg.get("type") != "ready":
        print("Alice: Bob not ready"); s.close(); return

    send_json(s, {"type":"qubits", "states": states})
    msg = recv_json(s)
    if msg.get("type") != "bob_bases":
        print("Alice: expected bob_bases"); s.close(); return
    bob_bases = msg["bob_bases"]

    send_json(s, {"type":"alice_bases", "alice_bases": alice_bases})
    msg = recv_json(s)
    if msg and msg.get("type") == "bob_results":
        bob_results = msg["bob_results"]

    sifted_indices = [i for i in range(min(len(alice_bases), len(bob_bases))) if alice_bases[i] == bob_bases[i]]
    sifted_alice = [str(alice_bits[i]) for i in sifted_indices]
    print("Alice: sifted key bits (Alice):", sifted_alice)

    # --- Eavesdropping detection ---
    msg = recv_json(s)
    if msg.get("type") == "test_indices":
        indices = msg["indices"]
        test_bits = [sifted_alice[i] for i in indices]
        send_json(s, {"type":"test_bits", "bits": test_bits})
        msg = recv_json(s)
        if msg.get("type") == "abort":
            print("Alice: Eve detected! aborting key."); s.close(); return
        elif msg.get("type") == "ok":
            print("Alice: key verified, safe to use")

    if sifted_alice:
        fernet_key = derive_fernet_key_from_bits(sifted_alice)
        cipher = Fernet(fernet_key)
        token = cipher.encrypt(args.message.encode())
        send_json(s, {"type":"enc", "token": token.decode()})
        ack = recv_json(s)
        print("Alice: server reply:", ack)
    s.close()

if __name__ == "__main__":
    main()
