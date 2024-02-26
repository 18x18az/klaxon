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

def playClip(clip):
    print(f'playing {clip} sound')
    playsound(f'{clip}.wav')

end_time = None
mode = None
pendingTimers = None

currentField = None

server = connect.get_server()

async def timer(time, sound):
    global pendingTimers
    # time is in ISO format
    timeToWait = (time - datetime.now(timezone.utc)).total_seconds()
    print(f'waiting {timeToWait} seconds to play {sound} sound')
    await asyncio.sleep(timeToWait)
    if sound != 'warning':
        pendingTimers = None
    playClip(sound)

def playWarning():
    playClip('warning')

def playStart():
    playClip('start')

def playPause():
    playClip('pause')

def playStop():
    playClip('stop')

async def process_field_control(set_mode, set_end_time):
    global mode, pendingTimers, end_time

    if set_mode == mode and set_end_time == end_time:
        return

    priorMode = mode

    hadPendingTimers = False

    if pendingTimers is not None:
        hadPendingTimers = True
        for pendingTimer in pendingTimers:
            pendingTimer.cancel()
        pendingTimers = None

    if hadPendingTimers:
        if priorMode == 'AUTO':
            playPause()
        else:
            playStop()

    mode = set_mode
    end_time = set_end_time

    if set_end_time is not None:
        playStart()
        end_datetime = datetime.fromisoformat(set_end_time)

        if mode == 'AUTO':
            pendingTimers = [asyncio.create_task(timer(end_datetime, 'pause'))]
        else:
            warning30Sec = end_datetime - timedelta(seconds=30)
            warning15Sec = end_datetime - timedelta(seconds=15)
            pendingTimers = [
                asyncio.create_task(timer(warning30Sec, 'warning')),
                asyncio.create_task(timer(warning15Sec, 'warning')),
                asyncio.create_task(timer(end_datetime, 'stop'))
                ]


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
