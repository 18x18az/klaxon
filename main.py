#!/usr/bin/env python3
import connect
import datetime
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport
import websockets
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from playsound import playsound

end_time = None
mode = None
pendingTimer = None

currentField = None

server = connect.get_server()

async def timer(stop_time: str, isWarning: bool = False):
    global pendingTimer, end_time
    # time is in ISO format
    timeToWait = (datetime.fromisoformat(stop_time) - datetime.now(timezone.utc)).total_seconds()
    if isWarning:
        timeToWait -= 30
    await asyncio.sleep(timeToWait)
    if isWarning:
        playWarning()
        pendingTimer = asyncio.create_task(timer(end_time))
    else:
        pendingTimer = None
        end_time = None
        periodEnd()

def playWarning():
    print('playing warning sound')
    playsound('warning.wav')

def playStart():
    print('playing start sound')
    playsound('start.wav')

def playPause():
    print('playing pause sound')
    playsound('pause.wav')

def playStop():
    print('playing stop sound')
    playsound('stop.wav')

def periodEnd():
    global mode
    if mode == 'AUTO':
        playPause()
    else:
        playStop()

async def process_field_control(set_mode, set_end_time):
    global end_time, mode

    if set_mode != mode:
        mode = set_mode

    if set_end_time != end_time:
        end_time = set_end_time
        if end_time is None:
            periodEnd()
            global pendingTimer
        else:
            if pendingTimer is not None:
                pendingTimer.cancel()
                pendingTimer = None
            if mode == 'AUTO':
                pendingTimer = asyncio.create_task(timer(end_time))
            else:
                pendingTimer = asyncio.create_task(timer(end_time, True))
            playStart()

async def subscribe(server, serverPort, fieldId: int):
    url = 'ws://' + server + ':' + str(serverPort) + '/graphql'
    transport = WebsocketsTransport(url=url)
    query = gql("""
    subscription FieldControl($fieldId: Int!) {
            fieldControl(fieldId: $fieldId) {
            endTime
            mode
        }
    }
    """)

    variables = {
        "fieldId": fieldId
    }

    async with Client(transport=transport) as session:
        print('Subscribed to field control')
        try:
            async for result in session.subscribe(query, variable_values=variables):
                print(result)
                await process_field_control(result['fieldControl']['mode'], result['fieldControl']['endTime'])
        except websockets.exceptions.ConnectionClosedError:
            print('Connection lost')
            return

async def pollActiveField(server, port):
    url = 'http://' + server + ':' + str(port) + '/graphql'
    transport = AIOHTTPTransport(url)

    query = gql("""
        query results {
            competitionInformation {
                liveField {
                    id
                    fieldControl {
                        endTime
                        mode
                    }
                }
            }
        }
        """)


    async with Client(transport=transport, fetch_schema_from_transport=True) as session:
        lastValue = None
        current_subscription = None
        while True:
            await asyncio.sleep(0.25)
            try:
                result = await session.execute(query)
                liveField = result['competitionInformation']['liveField']
            except aiohttp.client_exceptions.ClientConnectorError:
                if lastValue is not None:
                    print("Connection lost")
                    current_subscription.cancel()
                    lastValue = None
                continue
        
            if liveField is None:
                if lastValue is not None:
                    lastValue = None
                    current_subscription.cancel()
                    print("Unassigned")
                continue
        
            fieldId = int(liveField['id'])
            if fieldId is not lastValue:
                if current_subscription is not None:
                    current_subscription.cancel()
                lastValue = fieldId
                print(f"Live field is field with id {fieldId}")
                current_subscription = asyncio.create_task(subscribe(server, port, fieldId))

            fieldControl = liveField['fieldControl']

            if fieldControl is not None:
                await process_field_control(fieldControl['mode'], fieldControl['endTime'])

def doTheThing(server, port):
    while True:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(pollActiveField(server, port))
            loop.close()
        except aiohttp.client_exceptions.ClientConnectorError:
            continue

server, port = connect.get_server()

doTheThing(server, port)
