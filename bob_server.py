# bob_server.py
import socket, random
from qiskit import QuantumCircuit, Aer, execute
from qkd_utils import send_json, recv_json, derive_fernet_key_from_bits
from cryptography.fernet import Fernet

HOST = "0.0.0.0"   # listen on all interfaces
PORT = 65432       # choose a free port

def measure_state(prep_basis, prep_bit, measure_basis):
    qc = QuantumCircuit(1, 1)
    # prepare
    if prep_bit == 1:
        qc.x(0)
    if prep_basis == 'X':
        qc.h(0)
    # measure in bob's basis
    if measure_basis == 'X':
        qc.h(0)
    qc.measure(0, 0)
    backend = Aer.get_backend('qasm_simulator')
    res = execute(qc, backend, shots=1).result().get_counts()
    measured = int(list(res.keys())[0])
    return measured

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"Bob: Listening on {HOST}:{PORT} ...")
    conn, addr = s.accept()
    print("Bob: Connected by", addr)

    # 1) receive init
    msg = recv_json(conn)
    if not msg or msg.get("type") != "init":
        print("Bob: invalid init, exiting")
        conn.close(); return
    n = int(msg.get("num_qubits", 16))
    print("Bob: will process", n, "qubits")

    # 2) prepare bob's random bases
    bob_bases = [random.choice(['Z','X']) for _ in range(n)]

    # send ready message
    send_json(conn, {"type":"ready"})

    # 3) receive qubits (simulated classical description list)
    msg = recv_json(conn)
    if msg.get("type") != "qubits":
        print("Bob: expected 'qubits' message")
        conn.close(); return
    states = msg.get("states", [])
    if len(states) != n:
        print("Bob: mismatch in qubit count (got", len(states), "expected", n, ")")

    # 4) measure each received state using bob_bases
    bob_results = []
    for st, b_basis in zip(states, bob_bases):
        measured = measure_state(st['basis'], st['bit'], b_basis)
        bob_results.append(measured)

    # 5) send bob_bases to Alice (basis reconciliation starts)
    send_json(conn, {"type":"bob_bases", "bob_bases": bob_bases})

    # 6) receive alice_bases
    msg = recv_json(conn)
    if msg.get("type") != "alice_bases":
        print("Bob: expected alice_bases")
        conn.close(); return
    alice_bases = msg["alice_bases"]

    # 7) compute sifted key (positions where bases match)
    sifted_indices = [i for i in range(min(len(alice_bases), len(bob_bases))) if alice_bases[i] == bob_bases[i]]
    sifted_bob = [str(bob_results[i]) for i in sifted_indices]
    print("Bob: sifted key bits (Bob):", sifted_bob)

    # send bob_results optionally (for debug)
    send_json(conn, {"type":"bob_results", "bob_results": bob_results})

    # 8) derive symmetric key and wait for encrypted message
    if not sifted_bob:
        print("Bob: no sifted bits, cannot derive key")
    else:
        fernet_key = derive_fernet_key_from_bits(sifted_bob)
        cipher = Fernet(fernet_key)

        # wait for encrypted message
        msg = recv_json(conn)
        if msg and msg.get("type") == "enc":
            token = msg["token"].encode()
            try:
                plaintext = cipher.decrypt(token)
                print("Bob: Decrypted message from Alice:", plaintext.decode())
                send_json(conn, {"type":"ok", "msg":"decrypted"})
            except Exception as e:
                print("Bob: decryption failed:", e)
                send_json(conn, {"type":"error", "msg":"decryption failed"})
        else:
            print("Bob: no encrypted message received")

    conn.close()
    s.close()

if __name__ == "__main__":
    start_server()
