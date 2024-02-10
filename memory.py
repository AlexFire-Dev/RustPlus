class DataBase:
    def __init__(self):
        self.memory: dict = {}

    def add_record(self, notification: dict):

        ip = notification["ip"]
        port = notification["port"]
        address = f"{ip}:{port}"
        ntype = notification["type"]
        print(address, ntype)

        if ntype == "server":
            if address not in self.memory.keys():
                self.memory[address] = {
                    "name": notification["name"],
                    "url": notification["url"],
                    "player_id": notification["playerId"],
                    "player_token": notification["playerToken"],
                    "entities": {}
                }
        elif ntype == "entity":
            entity_id = notification["entityId"]
            if entity_id not in self.memory[address]["entities"].keys():
                self.memory[address]["entities"][entity_id] = {
                    "type": notification["entityType"],
                    "name": notification["entityName"]
                }

        print(self.memory)
