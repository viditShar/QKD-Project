import socket, random, argparse
from qkd_utils import send_json, recv_json

parser = argparse.ArgumentParser()
parser.add_argument("--listen_host", default="0.0.0.0")
parser.add_argument("--listen_port", type=int, default=65433)
parser.add_argument("--bob_host", required=True)
parser.add_argument("--bob_port", type=int, default=65432)
args = parser.parse_args()

def start_eve():
    s_eve = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s_eve.bind((args.listen_host, args.listen_port))
    s_eve.listen(1)
    print(f"Eve: Listening on {args.listen_host}:{args.listen_port} ...")
    conn_alice, addr_alice = s_eve.accept()
    print("Eve: Connected by Alice", addr_alice)

    s_bob = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s_bob.connect((args.bob_host, args.bob_port))
    print("Eve: Connected to Bob at", args.bob_host, args.bob_port)

    try:
        while True:
            msg = recv_json(conn_alice)
            if msg is None:
                break
            print("Eve intercepted:", msg)

            # --- simulate disturbance ---
            if msg.get("type") == "qubits":
                for st in msg["states"]:
                    eve_basis = random.choice(['Z','X'])
                    # if basis mismatch, flip bit randomly (50% chance)
                    if eve_basis != st['basis']:
                        st['bit'] = 1 - st['bit'] if random.random() < 0.5 else st['bit']

            send_json(s_bob, msg)
            resp = recv_json(s_bob)
            if resp is None:
                break
            send_json(conn_alice, resp)
    except Exception as e:
        print("Eve: error", e)
    finally:
        conn_alice.close(); s_bob.close(); s_eve.close()

if __name__ == "__main__":
    start_eve()
