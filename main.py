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
    client.subscribe('fieldSet/1')


def handle_field_set(field):
    global currentField
    if field and field != currentField:
        currentField = field
        print('Field set to ' + field)
        client.subscribe('fields/' + field)
    elif field == None and currentField:
        currentField = None
        client.unsubscribe('fields/' + currentField)
        print('No current field')

previous_state = "DISABLED"

class FieldState:
    def __init__(self) -> None:
        self.currentState = "DISABLED"
        self.timer = None
        self.endTime = None

    def handleDisable(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

        self.endTime = None
        self.currentState = "DISABLED"

    def playStartSound(self):
        playsound('start.wav')

    def handleAutonomousEnd(self):
        self.handleDisable()
        playsound('pause.wav')

    def handleDriverEnd(self):
        self.handleDisable()
        playsound('stop.wav')

    def handleEarlyEnd(self):
        self.handleDisable()
        playsound('stop.wav')

    def handleWarning(self):
        playsound('warning.wav')
        timeToEnd = self.endTime - datetime.datetime.now(tz=pytz.UTC)
        self.timer = threading.Timer(timeToEnd.total_seconds(), self.handleDriverEnd)
        self.timer.start()

    def handleFieldState(self, payload):
        state = payload['state']

        if state == self.currentState:
            return
        
        if state == "DISABLED":
            self.handleEarlyEnd()
            return
        
        self.playStartSound()

        self.endTime = datetime.datetime.fromisoformat(payload['endTime'])

        if state == "AUTO":
            timeToEnd = self.endTime - datetime.datetime.now(tz=pytz.UTC)
            self.timer = threading.Timer(timeToEnd.total_seconds(), self.handleAutonomousEnd)
            self.timer.start()
        else:
            # 30 second warning
            timeToWarning = self.endTime - datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(seconds=30)
            self.timer = threading.Timer(timeToWarning.total_seconds(), self.handleWarning)
            self.timer.start()

        self.currentState = state
        

field = FieldState()

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = json.loads(msg.payload.decode('utf-8'))
    if topic.startswith('fieldSet'):
        handle_field_set(payload['currentField'])

    elif topic.startswith('fields'):
        print(payload)
        field.handleFieldState(payload)

client = mqtt.Client(transport='websockets')

client.on_connect = on_connect
client.on_message = on_message

client.connect(server, 1883, 60)

client.loop_forever()
