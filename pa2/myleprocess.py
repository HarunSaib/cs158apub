import uuid
import json
import socket
import threading
import time



class Message:
    def __init__(self, uuid_val, flag=0):
        self.uuid = uuid_val # uuid being the ID passed around
        self.flag = flag # flag being whether or not the leader has been elected with the associated ID

    def uuid_to_dict(self):
        return {
            "uuid": str(self.uuid), 
            "flag": self.flag
                }

    def uuid_from_dict(data):
        return Message(
            uuid.UUID(data["uuid"])
            data["flag"]
        )


def read_config(filename="config.txt"):


    pass

def send_message(message):

    pass

def run_server():
    pass

def run_client():
    pass

def receive_loop():
    pass


def main():
    pass