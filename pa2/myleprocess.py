import uuid
import json
import socket
import threading
import time

process_uuid = uuid.uuid4()
leader_id = None
state = 0

client_connection = None
server_connection = None

class Message:
    def __init__(self, uuid_val, flag=0):
        self.uuid = uuid_val # uuid being the ID passed around
        self.flag = flag # flag being whether or not the leader has been elected with the associated ID

    # function to convert 'Message' class object into dict, to be converted into JSON and send
    def to_dict(self):
        return {
            "uuid": self.uuid, # store uuid as str(ing)
            "flag": self.flag # store flag as is
        } # pretty straight forward turning into dict

    # function to convert received dictionaty from json to 'Message' class object
    @staticmethod
    def from_dict(data):
        # Using our message class
        return Message(
            # We first derive (and convert to UUID obj) the uuid from the data dictionaty
            uuid.UUID(data["uuid"]),
            # Then we fetch the flag
            data["flag"]
        ) # And return as a message object


def read_config(filename="config.txt"):
    with open(filename, "r") as file: # grab the file from the name passed in
        # create list of lines in the file, strip()-ping whitespaces 
        lines = [line.strip() for line in file if line.strip()] 

    # small helper to unpack lines from the list
    def parse_address(line):
        ip, port = line.splot(",") # fetch ip and port seperated by comma
        return ip.strip(), port.strip() # clean up whitespaces
    
    return parse_address(lines[0]), parse_address(lines[1])

# function to convert the processed uuid and flag dict into json and send to client
def send_message(message):
    data = message.to_dict() # turning the message into data to send as a dict
    json_text = json.dumps(data) + "\n" # serializaing the data as json (adduing a newline)

    # using .encode() turns the python sting into bytes (essentially adding the b'{...}\n' from slides)
    # then we send said bytes to the connected client, from myself (the server)
    client_connection.sendall(json_text.encode())

    print(f"Sent: uuid={message.uuid}, flag={message.flag}")

# function to listen and connect to any incoming requested addresses
def run_server(local_address):
    global server_connection # Socket connection for receiving to the server's (me) IP and port
    
    # Creates 'server_socket', which is a TCP socket that listens for incoming IPv4 address connections
    server_socket = socket.socket(
        socket.AF_INET, # AF_NET means IPv4 standard for IP addresses
        socket.SOCK_STREAM # SOCK_STREAM means TCP
    )

    # Configures the the socket before it binds to an IP and port
    server_socket.setsockopt(
        # SOL_SOCKET is where the general socket settings are, so we're modfying a var in there
        socket.SOL_SOCKET, 
        # SO_REUSEADDR is the var, this flag allows the reuse of same IP and port after it recently closed
        socket.SO_REUSEADDR,
        # 1 just sets that flag to true, enabling it :)
        1
    )

    # this assigns the server socket to the IP address and port from config.txt (passed in)
    server_socket.bind(local_address)
    # this starts listening/waiting for incoming TCP connections, the 1 being the queue size allowed to wait
    server_socket.listen(1)

    # This waits until we have a socket asking to connect, once it does we fetch the connection and address
    # these are used in the receive_loop() function
    server_connection, address = server_socket.accept()

    print(f"Accepted connection from {address}")

def run_client(next_address):
    global client_connection # Socket connection for sending to the client's (neighbor) IP and port 

    time.sleep(2) # Sleep to allow the other processes time to execute, no deadlock

    # Once again creating a TCP socket, this time a client side, that sends out an IPv4 connection
    client_connection = socket.socket(
        socket.AF_INET, # AF_NET means IPv4 standard for IP addresses
        socket.SOCK_STREAM # SOCK_STREAM means TCP
    )

    # Sends out a connection request to the client (neighbor) (passed in) 
    client_connection.connect(next_address)

    # Once connected, create and send a message object including my process uuid and the election flag.
    initial_message = Message(process_uuid, 0)
    send_message(initial_message)

def receive_loop():
    global state, leader_id
    
    buffer = ""

    while True:
        received_bytes = server_connection.recv(1024)

        if not received_bytes:
            break

        buffer += received_bytes.decode()

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)

            if not line:
                continue

            data = json.loads(line)
            message = Message.from_dict(data)

            print(
                f"Received: uuid={message.uuid},"
                f"flag={message.flag}"
            )

            if message.flag == 0:
                if state == 1:
                    continue
                    
                if message.uuid > process_uuid:
                    send_message(message)

                elif message.uuid == process_uuid:
                    leader_id = process_uuid
                    state = 1
                    send_message(Message(process_uuid, 1))

                else:
                    print(f"Ignored smaller UUID: {message.uuid}")

            elif message.flag == 1:
                leader_id = message.uuid
                state = 1

                if message.uuid == process_uuid:
                    break
                else:
                    send_message(message)
                    break
        if state == 1 and leader_id is not None:
            print(f"Leader is {leader_id}")


def main():
    pass