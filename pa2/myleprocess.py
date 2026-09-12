import uuid
import json
import socket
import threading
import time



class Message:
    def __init__(self, uuid_val, flag=0):
        self.uuid = uuid_val # uuid being the ID passed around
        self.flag = flag # flag being whether or not the leader has been elected with the associated ID

    # function to convert 'Message' class object into dict, to be converted into JSON and send
    def to_dict(self):
        return {
            "uuid": str(self.uuid), # store uuid as str(ing)
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