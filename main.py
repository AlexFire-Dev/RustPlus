import time

import discord
from discord import Message, Intents

from conf import conf
from fcm import FCM, fcm_details
from memory import DataBase


BOT_TOKEN = conf.BOT_TOKEN


class MyClient(discord.Client):
    def fcm_callback(self, notification):
        self.database.add_record(notification)

    async def on_ready(self):
        print('------')
        print('Logged on as {0}!'.format(self.user))
        print('------\nServers:')
        for guild in self.guilds:
            print(guild)
        print('------\nSetting up rust+ features')
        print("DataBase   ", end=' ')
        try:
            self.database: DataBase = DataBase()
            print("=> OK!")
        except Exception as e:
            print("=> FAIL!")
        print("FCM Manager", end=' ')
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
                time.sleep(5)
                await message.delete()

            return

        print('Message:', f'Text: {message.content}', f'Server: {message.guild}')

        # if message.content.startswith(f'{PREFIX}hello'):
        #     await commands.hello_world(message)
        #     return


intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(BOT_TOKEN)
