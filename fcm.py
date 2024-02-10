from rustplus import FCMListener

from threading import Thread
import json


with open("conf/rustplus.py.config.json", "r") as input_file:
    fcm_details = json.load(input_file)


class FCM(FCMListener):
    def __init__(self, *args, callback=None):
        super().__init__(*args)
        self.callback = callback

    def start(self, daemon=True) -> None:
        self.thread = Thread(target=self.__fcm_listen, daemon=daemon)
        self.thread.start()

    def __fcm_listen(self) -> None:
        if self.data is None:
            raise ValueError("Data is None")

        self._push_listener.listen(callback=self.on_notification)

    def on_notification(self, obj, notification, data_message):
        self.callback(json.loads(notification.get("data").get("body")))
