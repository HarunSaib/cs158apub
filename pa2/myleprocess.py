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

def run_server():
    pass

def run_client():
    pass

def receive_loop():
    pass


def main():
    pass