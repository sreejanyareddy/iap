import socket
import threading
import bcrypt

HOST = '0.0.0.0'
PORT = 5000

lock = threading.Lock()

USER_DB = "users.db"

def load_users():
    users = {}
    try:
        with open(USER_DB, "r") as f:
            for line in f:
                username, hashed = line.strip().split(":")
                users[username] = hashed.encode()
    except FileNotFoundError:
        pass
    return users

def save_user(username, hashed):
    with open(USER_DB, "a") as f:
        f.write(f"{username}:{hashed.decode()}\n")

# ✅ LOAD USERS AT STARTUP
users = load_users()

authenticated = {}   # socket -> username
active_users = set() # logged-in usernames


def handle_auth(client_socket):
    try:
        data = client_socket.recv(1024).decode().strip()
        parts = data.split()

        if len(parts) != 3:
            client_socket.send(b"ERROR Invalid command format\n")
            return None

        command, username, password = parts
        command = command.upper()
        password = password.encode()

        with lock:
            if command == "REGISTER":
                if username in users:
                    client_socket.send(b"ERROR User already exists\n")
                    return None

                hashed = bcrypt.hashpw(password, bcrypt.gensalt())
                users[username] = hashed
                save_user(username, hashed)

                client_socket.send(b"OK Registered successfully\n")
                return None

            elif command == "LOGIN":
                if username not in users:
                    client_socket.send(b"ERROR Invalid credentials\n")
                    return None

                if not bcrypt.checkpw(password, users[username]):
                    client_socket.send(b"ERROR Invalid credentials\n")
                    return None

                if username in active_users:
                    client_socket.send(b"ERROR User already logged in\n")
                    return None

                active_users.add(username)
                authenticated[client_socket] = username
                client_socket.send(b"OK Login successful\n")
                return username

            else:
                client_socket.send(b"ERROR Unknown command\n")
                return None

    except:
        return None


def broadcast(message, sender_socket):
    with lock:
        sender = authenticated.get(sender_socket, "unknown")
        tagged = f"{sender}: {message.decode()}".encode()

        for client in list(authenticated.keys()):
            if client != sender_socket:
                try:
                    client.sendall(tagged)
                except:
                    logout(client)


def logout(client_socket):
    with lock:
        username = authenticated.pop(client_socket, None)
        if username:
            active_users.discard(username)
    client_socket.close()


def handle_client(client_socket, client_address):
    print(f"[+] Connection from {client_address}")

    while True:
        username = handle_auth(client_socket)
        if username:
            break

    print(f"[AUTH] {username} logged in")

    try:
        while True:
            message = client_socket.recv(1024)
            if not message:
                break
            broadcast(message, client_socket)
    finally:
        print(f"[-] {username} disconnected")
        logout(client_socket)


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()

    print(f"[SERVER] Listening on {HOST}:{PORT}")

    while True:
        client_socket, client_address = server_socket.accept()
        threading.Thread(
            target=handle_client,
            args=(client_socket, client_address),
            daemon=True
        ).start()


if __name__ == "__main__":
    start_server()
