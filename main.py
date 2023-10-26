#!/usr/bin/env python3
import pytz
import connect
import paho.mqtt.client as mqtt
import json
import datetime
import threading
from playsound import playsound

currentField = None

server = connect.get_server()

def on_connect(client, userdata, flags, rc):
    print('Connected to MQTT server')
    client.subscribe('fieldControl')

class FieldState:
    def __init__(self) -> None:
        self.state = "DISABLED"
        self.timer = None
        self.endTime = None

    def handleDisable(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

        self.endTime = None
        self.state = "DISABLED"

    def playStartSound(self):
        playsound('start.wav')

    def handleAutonomousEnd(self):
        self.handleDisable()
        playsound('pause.wav')

    def handleDriverEnd(self):
        self.handleDisable()
        playsound('stop.wav')

    def handleEarlyEnd(self):
        print('handling early end')
        self.handleDisable()
        playsound('stop.wav')

    def handleWarning(self):
        playsound('warning.wav')
        timeToEnd = self.endTime - datetime.datetime.now(tz=pytz.UTC)
        self.timer = threading.Timer(timeToEnd.total_seconds(), self.handleDriverEnd)
        self.timer.start()

    def handleFieldState(self, payload):
        state = payload['state']
        print(state)

        if state == 'AUTO':
            if self.state == 'ENABLED':
                return
            print('auto started')
            self.state = "ENABLED"
            self.playStartSound()
            self.endTime = datetime.datetime.strptime(payload['time'], '%Y-%m-%dT%H:%M:%S.%f%z')
            timeToEnd = self.endTime - datetime.datetime.now(tz=pytz.UTC)
            self.timer = threading.Timer(timeToEnd.total_seconds(), self.handleAutonomousEnd)
            self.timer.start()
        elif state == 'DRIVER':
            if self.state == 'ENABLED':
                return
            print('driver started')
            self.endTime = datetime.datetime.strptime(payload['time'], '%Y-%m-%dT%H:%M:%S.%f%z')
            self.state = "ENABLED"
            self.playStartSound()
            timeToWarning = self.endTime - datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(seconds=30)
            self.timer = threading.Timer(timeToWarning.total_seconds(), self.handleWarning)
            self.timer.start()
        elif self.state == "ENABLED":
            print('received something indicating the match is over while enabled')
            self.handleEarlyEnd()

field = FieldState()

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = json.loads(msg.payload.decode('utf-8'))
    field.handleFieldState(payload)

client = mqtt.Client(transport='websockets')

client.on_connect = on_connect
client.on_message = on_message

client.connect(server, 1883, 60)

client.loop_forever()
