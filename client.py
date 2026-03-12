import socket
import threading
import sys
import ssl

HOST = "localhost"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5005


# ---------------- TLS CONFIG ----------------

def create_ssl_context():
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations("server.crt")
    return context


# Thread to receive messages from server
def receive_messages(sock):
    while True:
        try:
            msg = sock.recv(1024)

            if not msg:
                print("\nServer disconnected.")
                break

            print("\n" + msg.decode())
        except Exception:
            break


# Authentication (REGISTER / LOGIN)
def authenticate(sock):
    while True:
        try:
            prompt = sock.recv(1024).decode().strip()
            print(prompt, end=" ", flush=True)
            command = input().strip()
            sock.sendall(command.encode())

            prompt = sock.recv(1024).decode().strip()
            print(prompt, end=" ", flush=True)
            username = input().strip()
            sock.sendall(username.encode())

            prompt = sock.recv(1024).decode().strip()
            print(prompt, end=" ", flush=True)
            password = input().strip()
            sock.sendall(password.encode())

            response = sock.recv(1024).decode().strip()
            print(response)

            if response.startswith("ERROR"):
                continue

            if response.startswith("OK") and command.upper() == "LOGIN":
                print("\nAvailable Commands:")
                print("SEND <ROOM> <message>")
                print("/join <room>")
                print("/leave")
                print("/rooms")
                print("/myrooms")
                print("/subscribe <username>")
                print("/unsubscribe <username>")
                print("exit\n")
                break

        except Exception as e:
            print("Connection lost:", e)
            return False

    return True


# Thread to send messages
def send_messages(sock):
    while True:
        try:
            msg = input()

            if msg.lower() == "exit":
                sock.sendall(b"EXIT")
                break

            sock.sendall(msg.encode())

        except Exception:
            break


def main():
    try:

        context = create_ssl_context()

        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        sock = context.wrap_socket(
            raw_sock,
            server_hostname=HOST
        )

        sock.connect((HOST, PORT))

        success = authenticate(sock)

        if not success:
            sock.close()
            return

        recv_thread = threading.Thread(target=receive_messages, args=(sock,), daemon=True)
        send_thread = threading.Thread(target=send_messages, args=(sock,))

        recv_thread.start()
        send_thread.start()

        send_thread.join()

        sock.close()
        print("Client exited.")

    except Exception as e:
        print("Unable to connect to server:", e)


if __name__ == "__main__":
    main()