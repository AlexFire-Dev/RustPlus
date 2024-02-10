from rustplus import FCMListener
import json

with open("conf/rustplus.py.config.json", "r") as input_file:
    fcm_details = json.load(input_file)


class FCM(FCMListener):
    def __init__(self, *args, callback=None):
        super().__init__(*args)
        self.callback = callback

    def on_notification(self, obj, notification, data_message):
        # try:
        self.callback(json.loads(notification.get("data").get("body")))
        # except Exception as error:
        #     print(f"Error: {error}")
