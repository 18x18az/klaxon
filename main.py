#!/usr/bin/env python3
import pytz
import connect
import paho.mqtt.client as mqtt
import datetime
import threading
from playsound import playsound
import json

currentField = None

server = connect.get_server()

def on_connect(client, userdata, flags, rc):
    print('Connected to MQTT server')
    client.subscribe('liveField')

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
        print('playing start sound')
        playsound('start.wav')

    def handleAutonomousEnd(self):
        self.handleDisable()
        print('auto ended')
        playsound('pause.wav')

    def handleDriverEnd(self):
        self.handleDisable()
        print('driver ended')
        playsound('stop.wav')

    def handleEarlyEnd(self):
        print('handling early end')
        self.handleDisable()
        playsound('stop.wav')

    def handleWarning(self):
        playsound('warning.wav')
        print('playing 30 second warning')
        timeToEnd = self.endTime - datetime.datetime.now(tz=pytz.UTC)
        self.timer = threading.Timer(timeToEnd.total_seconds(), self.handleDriverEnd)
        self.timer.start()

    def handleFieldState(self, payload):
        mode = payload['mode']
        endTime = payload['endTime']

        if self.state == 'ENABLED' and endTime == None:
            print('match over')
        elif self.state != 'ENABLED' and endTime != None:
            if mode == 'AUTO':
                print('auto started')
                self.state = "ENABLED"
                self.playStartSound()
                self.endTime = datetime.datetime.strptime(endTime, '%Y-%m-%dT%H:%M:%S.%f%z')
                timeToEnd = self.endTime - datetime.datetime.now(tz=pytz.UTC)
                self.timer = threading.Timer(timeToEnd.total_seconds(), self.handleAutonomousEnd)
                self.timer.start()
            elif mode == 'DRIVER':
                print('driver started')
                self.endTime = datetime.datetime.strptime(endTime, '%Y-%m-%dT%H:%M:%S.%f%z')
                self.state = "ENABLED"
                self.playStartSound()
                timeToWarning = self.endTime - datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(seconds=30)
                self.timer = threading.Timer(timeToWarning.total_seconds(), self.handleWarning)
                self.timer.start()

field = FieldState()

def on_message(client, userdata, msg):
    topic = msg.topic
    global currentField
    if topic == 'liveField':
        payload = json.loads(msg.payload.decode('utf-8'))
        fieldId = payload['fieldId']
        if fieldId != currentField:
            print('field is now ' + str(fieldId))
            if currentField is not None:
                client.unsubscribe('fieldControl/' + str(currentField))
            currentField = fieldId
            if currentField is not None:
                client.subscribe('fieldControl/' + str(currentField))
    elif topic == 'fieldControl/' + str(currentField):
        payload = json.loads(msg.payload.decode('utf-8'))
        field.handleFieldState(payload)
    #field.handleFieldState(payload)

client = mqtt.Client(transport='websockets')

client.on_connect = on_connect
client.on_message = on_message

client.connect(server, 1883, 60)

client.loop_forever()
