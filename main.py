import json
import time
import sys

import asyncio

import discord
from discord import Message, Intents

from rustplus import RustSocket

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

    def fcm_callback(self, notification):
        async def check_entity(socket: RustSocket, entity_id: str) -> bool:
            await socket.connect()

            try:
                info = await socket.get_entity_info(int(entity_id))
                print(f'Entity {entity_id} succeeded')
                result = True
            except Exception as e:
                print(f'Entity {entity_id} failed')
                result = False
            finally:
                await socket.disconnect()
            return result

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
            if not (asyncio.run(check_entity(self.sockets[ret["address"]], ret["entity_id"]))):
                self.database.memory[ret["address"]]["entities"].pop(ret["entity_id"])

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
        print("FCM Manager ", end=' ')
        try:
            self.fcm_manager: FCM = FCM(fcm_details, callback=self.fcm_callback)
            self.fcm_manager.start()
            print("=> OK!")
        except Exception as e:
            print("=> FAIL!")
        print('------')



    async def on_message(self, message: Message):
        if message.author.bot:
            if message.author == self.user:
                await asyncio.sleep(60)
                await message.delete()

            return

        print(f'Message: {message.content}', f'Server: {message.guild}')

        if message.content.startswith(f'memory'):
            await message.delete()
            await message.channel.send(json.dumps(self.database.memory, indent=4))
            return

        elif message.content.startswith(f'exit'):
            await message.delete()
            try:
                self.fcm_manager.thread.join(timeout=1)
            except:
                pass
            finally:
                sys.exit(0)



intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(BOT_TOKEN)
