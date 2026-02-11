import socket
import threading

HOST = 'localhost'
PORT = 5000


def receive_messages(sock):
    while True:
        try:
            msg = sock.recv(1024).decode()
            if not msg:
                break
            print(msg)
        except:
            break


def send_messages(sock):
    while True:
        try:
            msg = input()

            if msg.startswith("send "):
                actual_msg = msg[5:]  # remove "send "
                sock.sendall(actual_msg.encode())
            elif msg == "exit":
                sock.close()
                break
            else:
                print('Use: send <message> or exit')
        except:
            break


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    while True:
        command = input("Enter command (REGISTER / LOGIN): ").strip().upper()
        username = input("Username: ")
        password = input("Password: ")

        auth_msg = f"{command} {username} {password}"
        sock.sendall(auth_msg.encode())

        response = sock.recv(1024).decode()
        print(response)

        if response.startswith("OK") and command == "LOGIN":
            print("You can now broadcast messages.")
            print('Type: send <message>  to broadcast the message\n')
            break

    threading.Thread(target=receive_messages, args=(sock,), daemon=True).start()
    threading.Thread(target=send_messages, args=(sock,), daemon=True).start()

    while True:
        pass


if __name__ == "__main__":
    main()
