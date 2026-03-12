import socket
import threading
import bcrypt
import redis
import sys
import ssl

HOST = "0.0.0.0"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5005
SERVER_ID = f"SERVER-{PORT}"

lock = threading.Lock()

redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)

USER_DB = "users.db"

authenticated = {}   # socket -> username
user_rooms = {}   # username -> set of rooms


# ---------------- TLS CONFIG ----------------

def create_ssl_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")
    return context


# ---------------- USER DATABASE ----------------

def load_users():
    users = {}
    try:
        with open(USER_DB, "r") as f:
            for line in f:
                username, hashed = line.strip().split(":", 1)
                users[username] = hashed.encode()
    except FileNotFoundError:
        pass
    return users


def save_user(username, hashed):
    with open(USER_DB, "a") as f:
        f.write(f"{username}:{hashed.decode()}\n")


users = load_users()

# Clear stale sessions
redis_client.delete("sessions")


# ---------------- AUTHENTICATION ----------------

def handle_auth(client_socket):

    while True:

        client_socket.send(b"Enter command (REGISTER / LOGIN): ")
        command = client_socket.recv(1024)

        if not command:
            return None

        command = command.decode().strip().upper()

        if command not in ["REGISTER", "LOGIN"]:
            client_socket.send(b"ERROR Invalid command\n")
            continue

        client_socket.send(b"Username: ")
        username = client_socket.recv(1024).decode().strip()

        client_socket.send(b"Password: ")
        password = client_socket.recv(1024).decode().strip().encode()

        with lock:

            if command == "REGISTER":

                if username in users:
                    client_socket.send(b"ERROR User exists\n")
                    continue

                hashed = bcrypt.hashpw(password, bcrypt.gensalt())
                users[username] = hashed
                save_user(username, hashed)

                client_socket.send(b"OK Registered\n")
                continue


            if command == "LOGIN":

                if username not in users:
                    client_socket.send(b"ERROR Invalid credentials\n")
                    continue

                if not bcrypt.checkpw(password, users[username]):
                    client_socket.send(b"ERROR Invalid credentials\n")
                    continue

                if redis_client.hexists("sessions", username):
                    client_socket.send(b"ERROR User already logged in\n")
                    continue

                authenticated[client_socket] = username

                redis_client.hset("sessions", username, SERVER_ID)

                redis_client.sadd("room:lobby", username)

                user_rooms[username] = {"lobby"}
                redis_client.sadd("room:lobby", username)
                redis_client.sadd(f"userrooms:{username}", "lobby")

                print(f"[{SERVER_ID}] {username} logged in")

                client_socket.send(b"OK Login successful\n")

                return username


# ---------------- REDIS MESSAGE PUBLISH ----------------

def publish_message(sender, room, message):

    payload = f"{sender}|{room}|{message}"

    redis_client.publish("chat", payload)

    print(f"[{SERVER_ID}] Published → {payload}")


# ---------------- REDIS LISTENER ----------------

def redis_listener():

    pubsub = redis_client.pubsub()
    pubsub.subscribe("chat")

    for msg in pubsub.listen():

        if msg["type"] != "message":
            continue

        sender, room, message = msg["data"].split("|", 2)

        formatted = f"{sender}: {message}".encode()

        with lock:

            for client, username in authenticated.items():

                # Skip sender
                if username == sender:
                    continue

                # Check if user belongs to the room
                if room not in user_rooms.get(username, set()):
                    continue

                # Check subscription
                subs = redis_client.smembers(f"subs:{username}")

                if sender not in subs:
                    continue

                try:
                    client.sendall(formatted)
                except:
                    pass
# ---------------- LOGOUT ----------------

def logout(client_socket):

    with lock:

        username = authenticated.pop(client_socket, None)

        if username:

            # Remove session from Redis
            redis_client.hdel("sessions", username)

            # Get all rooms the user belongs to
            rooms = user_rooms.get(username, set())

            # Remove user from every room
            for room in rooms:
                redis_client.srem(f"room:{room}", username)

            # Remove user's room list from Redis
            redis_client.delete(f"userrooms:{username}")

            # Remove subscription list
            redis_client.delete(f"subs:{username}")

            # Remove from local memory
            user_rooms.pop(username, None)

            print(f"[{SERVER_ID}] {username} disconnected")

    client_socket.close()


# ---------------- CLIENT HANDLER ----------------

def handle_client(client_socket, address):

    print(f"[{SERVER_ID}] Connection from {address}")

    username = handle_auth(client_socket)

    try:

        while True:

            data = client_socket.recv(1024)

            if not data:
                break

            parts = data.decode().strip().split()

            command = parts[0].upper()


            if command == "EXIT":

                client_socket.send(b"Goodbye\n")
                break


            # JOIN ROOM
            elif command == "/JOIN" and len(parts) > 1:

             room = parts[1]
            
             redis_client.sadd(f"room:{room}", username)
            
             user_rooms.setdefault(username, set()).add(room)
            
             redis_client.sadd(f"userrooms:{username}", room)
            
             client_socket.send(f"Joined room {room}\n".encode())


            # LEAVE SPECIFIC ROOM
            elif command == "/LEAVE" and len(parts) > 1:

                room = parts[1]

                if room not in user_rooms.get(username, set()):
                    client_socket.send(f"You are not in room {room}\n".encode())
                    continue

                redis_client.srem(f"room:{room}", username)

                user_rooms[username].remove(room)

                redis_client.srem(f"userrooms:{username}", room)

                client_socket.send(f"Left room {room}\n".encode())


            # SHOW ALL AVAILABLE ROOMS
            elif command == "/ROOMS":

                rooms = []

                for key in redis_client.keys("room:*"):
                    if redis_client.scard(key) > 0:
                        rooms.append(key.split(":")[1])

                client_socket.send(f"Rooms: {', '.join(rooms)}\n".encode())


            # SHOW ROOMS USER BELONGS TO
            elif command == "/MYROOMS":

                rooms = user_rooms.get(username, set())

                if not rooms:
                    client_socket.send(b"You are not in any rooms\n")
                else:
                    client_socket.send(
                        f"You are in rooms: {', '.join(rooms)}\n".encode()
                    )


            # SUBSCRIBE TO USER
            elif command == "/SUBSCRIBE" and len(parts) > 1:

                target = parts[1]

                redis_client.sadd(f"subs:{username}", target)

                client_socket.send(f"Subscribed to {target}\n".encode())


            # UNSUBSCRIBE
            elif command == "/UNSUBSCRIBE" and len(parts) > 1:

                target = parts[1]

                redis_client.srem(f"subs:{username}", target)

                client_socket.send(f"Unsubscribed from {target}\n".encode())


            # SEND MESSAGE TO SPECIFIC ROOM
            elif command == "SEND" and len(parts) > 2:

                room = parts[1]
                msg = " ".join(parts[2:])

                if room not in user_rooms.get(username, set()):
                    client_socket.send(f"You are not in room {room}\n".encode())
                    continue

                publish_message(username, room, msg)


            else:

                client_socket.send(b"Unknown command\n")

    finally:

        logout(client_socket)

# ---------------- SERVER START ----------------

def start_server():

    ssl_context = create_ssl_context()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server.bind((HOST, PORT))
    server.listen()

    print(f"[{SERVER_ID}] TLS Chat Server listening on port {PORT}")

    threading.Thread(target=redis_listener, daemon=True).start()

    while True:

        client_socket, addr = server.accept()

        try:
            secure_socket = ssl_context.wrap_socket(
                client_socket,
                server_side=True
            )

            threading.Thread(
                target=handle_client,
                args=(secure_socket, addr),
                daemon=True
            ).start()

        except ssl.SSLError as e:
            print("TLS handshake failed:", e)
            client_socket.close()


if __name__ == "__main__":
    start_server()