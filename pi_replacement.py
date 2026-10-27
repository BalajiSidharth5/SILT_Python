import socket

IPADDRESS = "127.0.0.1"
PORT = 5005

def main():
    r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    r.bind((IPADDRESS, PORT))
    while True:
        try:
            data, addr = r.recvfrom(1024)
            r.settimeout(1.0)
            print(data.decode("ascii"), "\n\n\n\n\n\n\n\n\n\n\n\n")
        except TimeoutError:
            print("Data did not arrive...")

main()