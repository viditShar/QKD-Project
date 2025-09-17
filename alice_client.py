# alice_client.py
import socket, random, time
from qkd_utils import send_json, recv_json, derive_fernet_key_from_bits
from cryptography.fernet import Fernet
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--host", required=True, help="Bob's IP or hostname")
parser.add_argument("--port", type=int, default=65432)
parser.add_argument("--num", type=int, default=16)
parser.add_argument("--message", default="Hello Bob, this is Alice!")
args = parser.parse_args()

def build_states(bits, bases):
    return [{"basis": b, "bit": int(bt)} for bt,b in zip(bits,bases)]

def main():
    host = args.host
    port = args.port
    n = args.num

    # generate alice bits and bases
    alice_bits = [random.randint(0,1) for _ in range(n)]
    alice_bases = [random.choice(['Z','X']) for _ in range(n)]
    states = build_states(alice_bits, alice_bases)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    print("Alice: connected to Bob at", host, port)

    # 1) send init
    send_json(s, {"type":"init", "num_qubits": n})

    # 2) wait for ready
    msg = recv_json(s)
    if not msg or msg.get("type") != "ready":
        print("Alice: Bob not ready")
        s.close(); return

    # 3) send qubits (classical description for simulation)
    send_json(s, {"type":"qubits", "states": states})

    # 4) receive bob_bases
    msg = recv_json(s)
    if msg.get("type") != "bob_bases":
        print("Alice: expected bob_bases")
        s.close(); return
    bob_bases = msg["bob_bases"]

    # 5) send alice_bases
    send_json(s, {"type":"alice_bases", "alice_bases": alice_bases})

    # 6) (optional) receive bob_results for debugging
    msg = recv_json(s)
    if msg and msg.get("type") == "bob_results":
        bob_results = msg["bob_results"]
    else:
        bob_results = None

    # 7) compute sifted key
    sifted_indices = [i for i in range(min(len(alice_bases), len(bob_bases))) if alice_bases[i] == bob_bases[i]]
    sifted_alice = [str(alice_bits[i]) for i in sifted_indices]
    print("Alice: sifted key bits (Alice):", sifted_alice)

    # 8) derive symmetric key and encrypt message
    if not sifted_alice:
        print("Alice: no sifted bits, aborting")
    else:
        fernet_key = derive_fernet_key_from_bits(sifted_alice)
        cipher = Fernet(fernet_key)
        token = cipher.encrypt(args.message.encode())
        send_json(s, {"type":"enc", "token": token.decode()})
        # wait for ack
        ack = recv_json(s)
        print("Alice: server reply:", ack)

    s.close()

if __name__ == "__main__":
    main()
