"""
docker run -itd --name wrun-eclipse-mosquitto -p 1884:1883 eclipse-mosquitto:1.6
docker container stop wrun-eclipse-mosquitto

pip install paho-mqtt
"""
import subprocess
import unittest

from wrun import mqtt

try:
    from paho.mqtt import client
    PAHO_MISSING = False
except ModuleNotFoundError:
    PAHO_MISSING = True


class MosquittoBroker:
    def __init__(self):
        subprocess.check_call("docker container start wrun-eclipse-mosquitto".split())
        print(" started")

    def stop(self):
        subprocess.check_call("docker container stop wrun-eclipse-mosquitto".split())
        print(" stopped")


@unittest.skipIf(PAHO_MISSING, "paho.mqtt missing")
class TestClient(unittest.TestCase):
    def setUp(self):
        self.real_broker = MosquittoBroker()
        self.proxy_broker = mqtt.Broker()

    def tearDown(self):
        self.proxy_broker.stop()
        self.real_broker.stop()

    def _process(self):
        self.proxy_broker.process()

    def test_connect_disconnect(self):
        c = client.Client()
        c.on_log = lambda client, userdata, level, buf: print("ON_LOG", client, userdata, level, buf)
        c.connect("localhost")
        self._process()
        self._process()
        self._process()
        c.disconnect()
        self._process()
        self._process()

    def test_publish(self):
        c = client.Client()
        c.on_log = lambda client, userdata, level, buf: print("ON_LOG", client, userdata, level, buf)
        c.connect("localhost")
        self._process()
        self._process()
        self._process()
        c.publish(topic="test", payload=b"my-message", qos=1)
        self._process()
        self._process()
        c.disconnect()
        self._process()
        self._process()

    def test_subscribe_and_receive_message(self):
        subscriber = client.Client()
        subscriber.received = []
        subscriber.on_log = lambda client, userdata, level, buf: print("ON_LOG", client, userdata, level, buf)
        subscriber.on_message = lambda _client, userdata, msg: _client.received.append(msg.payload)
        subscriber.connect("localhost")
        self._process()
        self._process()
        self._process()
        subscriber.subscribe("test")
        self._process()
        self._process()
        subscriber.loop_start()
        publisher = client.Client()
        publisher.on_log = lambda client, userdata, level, buf: print("ON_LOG", client, userdata, level, buf)
        publisher.connect("localhost")
        self._process()
        self._process()
        self._process()
        publisher.publish(topic="test", payload=b"my-message")
        self._process()
        self._process()
        self._process()
        self._process()
        publisher.disconnect()
        self._process()
        self._process()
        subscriber.loop_stop()
        subscriber.disconnect()
        self._process()
        self._process()
        self.assertEqual(subscriber.received, [b"my-message"])


@unittest.skipIf(PAHO_MISSING, "paho.mqtt missing")
class TestHuge(unittest.TestCase):
    def setUp(self):
        self.real_broker = MosquittoBroker()
        self.proxy_broker = mqtt.Broker()

    def tearDown(self):
        self.proxy_broker.stop()
        self.real_broker.stop()

    def _process(self):
        self.proxy_broker.process()

    def test_big_payload(self):
        subscriber = client.Client()
        subscriber.received = []
        subscriber.on_log = lambda client, userdata, level, buf: print("ON_LOG", client, userdata, level, buf)
        subscriber.on_message = lambda _client, userdata, msg: _client.received.append(msg.payload)
        subscriber.connect("localhost")
        self._process()
        self._process()
        self._process()
        subscriber.subscribe("test")
        self._process()
        self._process()
        subscriber.loop_start()
        publisher = client.Client()
        publisher.on_log = lambda client, userdata, level, buf: print("ON_LOG", client, userdata, level, buf)
        publisher.connect("localhost")
        self._process()
        self._process()
        self._process()
        payload = b"my-message" * 1000
        publisher.publish(topic="test", payload=payload)
        for idx in range(19):
            print(idx)
            self._process()
        publisher.disconnect()
        self._process()
        self._process()
        subscriber.loop_stop()
        subscriber.disconnect()
        self._process()
        self._process()
        self.assertEqual(subscriber.received, [payload])
