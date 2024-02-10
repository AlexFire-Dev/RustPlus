import json
import time
import sys

import asyncio

import discord
from discord import Message, Intents

from rustplus import RustSocket
from rustplus import EntityEvent, TeamEvent, ChatEvent

from conf import conf
from fcm import FCM, fcm_details
from memory import DataBase

BOT_TOKEN = conf.BOT_TOKEN


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.database: DataBase
        self.fcm_manager: FCM
        self.sockets: dict = {}

    @staticmethod
    async def check_entity(socket: RustSocket, entity_id: str):
        await socket.connect()

        try:
            info = await socket.get_entity_info(int(entity_id))
            print(f'Entity {entity_id} succeeded')
            result = info
        except Exception as e:
            print(f'Entity {entity_id} failed')
            result = False
        finally:
            await socket.disconnect()
        return result

    def fcm_callback(self, notification):

        ret = self.database.add_record(notification)
        if not ret: return

        if ret.get("type") == "server":
            self.sockets[f"{ret['ip']}:{ret['port']}"] = RustSocket(
                ret['ip'],
                ret['port'],
                ret['player_id'],
                ret['player_token']
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
        print(event.message)

    async def entity_handler(self, event: EntityEvent, server_key: str):
        print(event.type, event.entity_id, event.value)

    async def rust_events_subscribe(self):
        print("Events subscribing")

        for key in self.sockets.keys():
            socket: RustSocket = self.sockets[key]

            await socket.connect()
            print(await socket.get_team_chat())

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
        print('------')
        print('Logged on as {0}!'.format(self.user))
        print('------\nServers:')
        for guild in self.guilds:
            print(guild)

        print('------\nSetting up rust+ features')
        print("DataBase    ", end=' ')
        try:
            self.database: DataBase = DataBase()
            print("=> OK!")
        except Exception as e:
            print("=> FAIL!")

        print("Load Memory ", end=' ')
        try:
            self.database.load_memory()
            try:
                self.add_sockets()
                print("=> OK!")
            except:
                print("=> FAIL!")
        except:
            print("=> NO DUMP!")

        print("FCM Manager ", end=' ')
        try:
            self.fcm_manager: FCM = FCM(fcm_details, callback=self.fcm_callback)
            self.fcm_manager.start()
            print("=> OK!")
        except Exception as e:
            print("=> FAIL!")
        print('------')

        await asyncio.sleep(30)
        await self.check_entities()
        await asyncio.sleep(30)
        await self.rust_events_subscribe()

    async def on_message(self, message: Message):
        if message.author.bot:
            if message.author == self.user:
                await asyncio.sleep(60)
                await message.delete()

            return

        print(f'Message {message.content}')

        if message.content.startswith('memory'):
            await message.delete()
            await message.channel.send(json.dumps(self.database.memory, indent=4))
            return

        elif message.content.startswith("devices"):
            await message.delete()
            for key in self.database.memory.keys():
                await message.channel.send(self.database.memory[key]["name"])
                await message.channel.send(json.dumps(self.database.memory[key]["entities"], indent=4, sort_keys=True))
            return

        elif message.content.startswith(f'save'):
            await message.delete()
            await message.channel.send("Saving Data")
            self.database.save_memory()
            await message.channel.send("Saved")
            return

        elif message.content.startswith(f'terminate'):
            await message.delete()
            await message.channel.send("Shutting Down!")
            self.database.save_memory()
            self.fcm_manager.thread.join(timeout=1)
            sys.exit(0)


intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(BOT_TOKEN)
