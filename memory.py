import json

import discord


class DataBase:
    def __init__(self):
        self.memory: dict = {}
        self.discord_memory: dict = {}

    def save_memory(self):
        with open("conf/memory.json", "w") as file:
            json.dump(self.memory, fp=file, indent=2)
        with open("conf/discord_memory.json", "w") as file:
            json.dump(self.discord_memory, fp=file, indent=2)
        print("Memory dumped")

    def load_memory(self):
        temp = json.load(open("conf/memory.json", "r"))
        self.memory = temp

    def load_discord_memory(self):
        temp = json.load(open("conf/discord_memory.json", "r"))
        self.discord_memory = temp

    def add_record(self, notification: dict):

        ip = notification["ip"]
        port = notification["port"]
        address = f"{ip}:{port}"
        ntype = notification["type"]

        if ntype == "server":
            if address not in self.memory.keys():
                self.memory[address] = {
                    "ip": ip,
                    "port": port,
                    "name": notification["name"],
                    "url": notification["url"],
                    "player_id": notification["playerId"],
                    "player_token": notification["playerToken"],
                    "entities": {},
                    "type": ntype
                }
                return self.memory[address]
        elif ntype == "entity":
            entity_id = notification["entityId"]
            if entity_id not in self.memory[address]["entities"].keys():
                self.memory[address]["entities"][entity_id] = {
                    "address": address,
                    "entity_id": entity_id,
                    "entity_type": notification["entityType"],
                    "name": notification["entityName"],
                    "type": ntype,
                    "value": False
                }
                return self.memory[address]["entities"][entity_id]
