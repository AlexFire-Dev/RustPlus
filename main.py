import json
import time
import sys, os

import asyncio
from typing import Optional, Union

import discord
from discord import Message, Intents

from rustplus import RustSocket
from rustplus import EntityEvent, TeamEvent, ChatEvent
from rustplus import RustTime

from fcm import FCM, fcm_details
from memory import DataBase


BOT_TOKEN = os.getenv("BOT_TOKEN")


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.database: DataBase
        self.fcm_manager: FCM
        self.sockets: dict = {}

    def get_channel_by_address(self, address: str):
        uid = self.database.discord_memory[address]
        channel = discord.utils.get(self.get_all_channels(), id=uid)
        return channel

    @staticmethod
    async def check_entity(socket: RustSocket, entity_id: str):
        await socket.connect()

        try:
            info = await socket.get_entity_info(int(entity_id))
            print(f"Entity {entity_id} succeeded")
            result = info
        except Exception as e:
            print(f"Entity {entity_id} failed")
            result = False
        finally:
            await socket.disconnect()
        return result

    async def toggle_switch(self, uid: str):
        for key in self.database.memory.keys():
            for device in self.database.memory[key]["entities"].keys():
                entity = self.database.memory[key]["entities"][device]
                if (device == uid) or (entity["name"] == uid):

                    value = entity["value"]

                    socket = self.sockets[key]
                    if value:
                        await socket.turn_off_smart_switch(int(entity["entity_id"]))
                        return "Off"
                    else:
                        await socket.turn_on_smart_switch(int(entity["entity_id"]))
                        return "On"

    def fcm_callback(self, notification):

        ret = self.database.add_record(notification)
        if not ret: return

        if ret.get("type") == "server":
            self.sockets[f"{ret['ip']}:{ret['port']}"] = RustSocket(
                ret["ip"],
                ret["port"],
                ret["player_id"],
                ret["player_token"]
            )
        elif ret.get("type") == "entity":
            result = asyncio.run(self.check_entity(self.sockets[ret["address"]], ret["entity_id"]))
            if not result:
                self.database.memory[ret["address"]]["entities"].pop(ret["entity_id"])
            else:
                self.database.memory[ret["address"]]["entities"][ret["entity_id"]]["value"] = result.value

    def add_sockets(self):
        for key in self.database.memory.keys():
            self.sockets[key] = RustSocket(
                self.database.memory[key]["ip"],
                self.database.memory[key]["port"],
                self.database.memory[key]["player_id"],
                self.database.memory[key]["player_token"]
            )

    async def check_entities(self):
        print("------\nEntities Check started")
        for key_server in self.database.memory.keys():
            for key_entity in self.database.memory[key_server]["entities"].keys():
                result = await (self.check_entity(self.sockets[key_server], key_entity))
                if not result:
                    self.database.memory[key_server]["entities"].pop(key_entity)
                else:
                    self.database.memory[key_server]["entities"][key_entity]["value"] = result.value
        print("Entities Check finished\n------")

    async def chat_handler(self, event: ChatEvent, server_key: str):
        text = event.message.message
        args = text.split()

        if (text[0] != "!") and (text[0] != "#"):
            if server_key in self.database.discord_memory.keys():
                channel = self.get_channel_by_address(server_key)
                await channel.send(f"{event.message.name}: {text}")

        if args[0] == "!time":
            socket: RustSocket = self.sockets[server_key]
            time: RustTime = await socket.get_time()
            await socket.send_team_message(f"# Time is {time.time}")
            await socket.send_team_message(f"# Sunrise {time.sunrise}, Sunset {time.sunset}")

        elif args[0] == "!info":
            socket: RustSocket = self.sockets[server_key]
            info = await socket.get_info()
            await socket.send_team_message(f"# {info.players}/{info.max_players} players online, {info.queued_players} in queue.")

        elif args[0] == "!toggle":
            socket: RustSocket = self.sockets[server_key]
            try:
                res = await self.toggle_switch(args[-1])
                await socket.send_team_message(f"# {args[-1]} is now {res}")
            except Exception as e:
                await socket.send_team_message(f"# failed to toggle {args[-1]}")

    async def entity_handler(self, event: EntityEvent, server_key: str):
        print(event.type, event.entity_id, event.value)
        self.database.memory[server_key]["entities"][str(event.entity_id)]["value"] = event.value

    async def rust_events_subscribe(self):
        print("Events subscribing")

        for key in self.sockets.keys():
            socket: RustSocket = self.sockets[key]

            await socket.connect()
            # print(await socket.get_team_chat())

            @socket.chat_event
            async def chat(event: ChatEvent):
                await self.chat_handler(event=event, server_key=key)

            @socket.team_event
            async def team(event: TeamEvent):
                print(event)

            for ent in [int(x) for x in self.database.memory[key]["entities"]]:
                @socket.entity_event(ent)
                async def alarm(event: EntityEvent):
                    await self.entity_handler(event, server_key=key)

        print("Events subscribed")

    async def on_ready(self):
        await self.change_presence(status=discord.Status.dnd)

        print("------")
        print("Logged on as {0}!".format(self.user))
        print("------\nServers:")
        for guild in self.guilds:
            print(guild)

        print("------\nSetting up rust+ features")
        print("DataBase    ", end=" ")
        try:
            self.database: DataBase = DataBase()
            print("=> OK!")
        except Exception as e:
            print("=> FAIL!")

        print("Load Memory ", end=" ")
        try:
            self.database.load_memory()
            try:
                self.add_sockets()
                print("=> OK!")
            except:
                print("=> FAIL!")
        except:
            print("=> NO DUMP!")

        print("Load Discord", end=" ")
        try:
            self.database.load_discord_memory()
            print("=> OK!")
        except:
            print("=> NO DUMP!")

        print("FCM Manager ", end=" ")
        try:
            self.fcm_manager: FCM = FCM(fcm_details, callback=self.fcm_callback)
            self.fcm_manager.start()
            print("=> OK!")
        except Exception as e:
            print("=> FAIL!")
        print("------")

        await asyncio.sleep(30)
        await self.check_entities()
        await asyncio.sleep(30)
        await self.rust_events_subscribe()

        game = discord.Game("Rust")
        await self.change_presence(status=discord.Status.online, activity=game)

    async def on_message(self, message: Message):
        if message.author.bot:
            # if message.author == self.user:
            #     await asyncio.sleep(60)
            #     await message.delete()
            return

        print(f"Message {message.content}")

        if message.content.startswith("memory"):
            await message.delete()
            await message.channel.send("Discord Memory Dump")
            await message.channel.send(json.dumps(self.database.discord_memory, indent=4))
            await message.channel.send("Memory Dump")
            await message.channel.send(json.dumps(self.database.memory, indent=4))
            return

        elif message.content.startswith("devices"):
            await message.delete()
            for key in self.database.memory.keys():
                await message.channel.send(self.database.memory[key]["name"])
                await message.channel.send(json.dumps(self.database.memory[key]["entities"], indent=4, sort_keys=True))
            return

        elif message.content.startswith("save"):
            await message.delete()
            await message.channel.send("Saving Data")
            self.database.save_memory()
            await message.channel.send("Saved")
            return

        elif message.content.startswith("terminate"):
            await message.delete()
            await message.channel.send("Shutting Down!")
            self.database.save_memory()
            self.fcm_manager.thread.join(timeout=1)
            sys.exit(0)

        elif message.content.startswith("toggle"):
            await message.delete()

            try:
                result = await self.toggle_switch(uid=message.content.split()[-1])
                if not result: raise IndexError
                await message.channel.send(f"Switch is {result}")
            except Exception as e:
                await message.channel.send(f"Failed to toggle {message.content.split()[-1]}")

        elif message.content.startswith("bind"):
            await message.delete()
            try:
                server = self.database.memory[message.content.split()[-1]]
                self.database.discord_memory[f"{server['ip']}:{server['port']}"] = message.channel.id
                await message.channel.send(f"Binded to server {server['ip']}:{server['port']}")
            except:
                await message.channel.send(f"No such server {message.content.split()[-1]}")

        elif message.content.startswith("rename"):
            await message.delete()
            if message.channel.id in self.database.discord_memory.values():
                try:
                    args = message.content.split()
                    address = [i for i in self.database.discord_memory if
                               self.database.discord_memory[i] == message.channel.id][0]
                    name = self.database.memory[address]["entities"][args[1]]["name"]
                    self.database.memory[address]["entities"][args[1]]["name"] = args[2]
                    await message.channel.send(f"Entity {args[1]} name: {name} -> {args[2]}")
                except Exception as e:
                    await message.channel.send(f"Failed to change Entity's {args[1]} name")

        else:
            if message.channel.id in self.database.discord_memory.values():
                address = [i for i in self.database.discord_memory if self.database.discord_memory[i] == message.channel.id]
                socket = self.sockets[address[0]]

                await socket.send_team_message(f"# {message.author.display_name}: {message.content}")


intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(BOT_TOKEN)
