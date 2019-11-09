"""
docker run -itd --name wrun-eclipse-mosquitto -p 1883:1883 eclipse-mosquitto:1.6
docker container stop wrun-eclipse-mosquitto

pip install paho-mqtt

docker container start wrun-eclipse-mosquitto
python -m unittest tests.test_mqtt
docker container stop wrun-eclipse-mosquitto
"""
import time
import unittest

try:
    from paho.mqtt import client
    SKIP = False
except ModuleNotFoundError:
    SKIP = True


def on_message(c, userdata, msg):
    # print(str(msg.payload))
    c.received.append(msg.payload)


@unittest.skipIf(SKIP, "paho.mqtt missing")
class Test(unittest.TestCase):
    def test(self):
        subscriber = client.Client()
        subscriber.received = []
        subscriber.on_message = on_message
        subscriber.connect("localhost")
        subscriber.subscribe("test")
        subscriber.loop_start()
        publisher = client.Client()
        publisher.connect("localhost")
        publisher.publish(topic="test", payload=b"my-message")
        time.sleep(0.5)
        subscriber.loop_stop()
        self.assertTrue(subscriber.received)
        msg = subscriber.received.pop()
        self.assertEqual(msg, b"my-message")
