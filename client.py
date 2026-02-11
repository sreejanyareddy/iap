import socket
import threading

HOST = 'localhost'
PORT = 5000


def receive_messages(sock):
    while True:
        try:
            msg = sock.recv(1024)
            if not msg:
                print("Server disconnected.")
                break
            print(msg.decode())
        except:
            break


def send_messages(sock):
    while True:
        try:
            msg = input()

            if msg.startswith("send "):
                actual_msg = msg[5:]
                sock.sendall(actual_msg.encode())

            elif msg.lower() == "disconnect":
                print("Disconnecting...")
                sock.close()
                break

            else:
                print("Use: send <message> OR exit")

        except:
            break


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    # Authentication Phase
    while True:
        command = input("Enter command (REGISTER / LOGIN): ").strip().upper()
        username = input("Username: ")
        password = input("Password: ")

        auth_msg = f"{command} {username} {password}"
        sock.sendall(auth_msg.encode())

        response = sock.recv(1024).decode()
        print(response)

        if response.startswith("OK") and command == "LOGIN":
            print("Type send <message> to broadcast")
            print("Type exit to disconnect\n")
            break

    # Messaging Phase
    recv_thread = threading.Thread(target=receive_messages, args=(sock,))
    send_thread = threading.Thread(target=send_messages, args=(sock,))

    recv_thread.start()
    send_thread.start()

    send_thread.join()  # Wait until user disconnects


if __name__ == "__main__":
    main()
