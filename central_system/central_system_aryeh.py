"""
From https://github.com/mobilityhouse/ocpp/issues/86

You need to bring the ChargePoint created in on_connect() out of the scope of on_connect(). 
Then you can use a different task to interact with the the ChargePoint.

Here is an example of a CSMS that can can be controlled using an HTTP API. The HTTP API has 2 endpoints:

POST / - to change configuration for all connected chargers. It excepts a JSON body with the fields key and value.
POST /disconnect - to disconnect a charger. It expects a JSON body with the field id that contains the charger ID.
The HTTP server is running at port 8080. Here a few CURL examples:

$ curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"key":"MeterValueSampleInterval","value":"10"}' \
  http://localhost:8080/
$  curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"id":"CHARGE_POINT_1"}' \
  http://localhost:8080/disconnect
Here code of the CSMS with the HTTP API:
"""

import logging
import asyncio
import websockets
from charge_point import ChargePoint
from aiohttp import web
from functools import partial
import ssl
from ocpp.v16.enums import Action, RegistrationStatus
from ocpp.v16 import call_result, call

# set up logging
#logging.basicConfig(level=logging.NOTSET) # DEBUG)
logging.basicConfig(level=logging.INFO)
logging.getLogger('ocpp').setLevel(level=logging.INFO)
logging.getLogger('ocpp').addHandler(logging.StreamHandler())

# config
CERT_PATH = "cert/"
USE_WSS = True

if USE_WSS:
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(CERT_PATH + "fullchain.pem", CERT_PATH + "privkey.pem")

class CentralSystem:
    def __init__(self):
        self._chargers = {}

    def register_charger(self, cp: ChargePoint) -> asyncio.Queue:
        """ Register a new ChargePoint at the CSMS. The function returns a
        queue.  The CSMS will put a message on the queue if the CSMS wants to
        close the connection. 
        """
        queue = asyncio.Queue(maxsize=1)

        # Store a reference to the task so we can cancel it later if needed.
        task = asyncio.create_task(self.start_charger(cp, queue))
        self._chargers[cp] = task

        return queue

    async def start_charger(self, cp, queue):
        """ Start listening for message of charger. """
        try:
            await cp.start()
        except Exception as e:
            print(f"Charger {cp.id} disconnected: {e}")
        finally:
            # Make sure to remove referenc to charger after it disconnected.
            del self._chargers[cp]

            # This will unblock the `on_connect()` handler and the connection
            # will be destroyed.
            await queue.put(True)

    async def change_configuration(self, key: str, value: str):
        for cp in self._chargers:
            await cp.change_configuration(key, value)

    def disconnect_charger(self, id: str):
        for cp, task in self._chargers.items():
            if cp.id == id:
                task.cancel()
                return 

        raise ValueError(f"Charger {id} not connected.")


async def change_config(request):
    """ HTTP handler for changing configuration of all charge points. """
    data = await request.json()
    csms = request.app["csms"]
    await csms.change_configuration(data["key"], data["value"])
    return web.Response()


async def disconnect_charger(request):
    """ HTTP handler for disconnecting a charger. """
    data = await request.json()
    csms = request.app["csms"]

    try:
        csms.disconnect_charger(data["id"])
    except ValueError as e:
        print(f"Failed to disconnect charger: {e}")
        return web.Response(status=404)

    return web.Response()


async def on_connect(websocket, path, csms):
    """ For every new charge point that connects, create a ChargePoint instance
    and start listening for messages.
    The ChargePoint is registered at the CSMS.
    """
    charge_point_id = path.strip("/")
    cp = ChargePoint(charge_point_id, websocket)

    print(f"Charger {cp.id} connected.")

    # If this handler returns the connection will be destroyed. Therefore we need some
    # synchronization mechanism that blocks until CSMS wants to close the connection.
    # An `asyncio.Queue` is used for that.
    queue = csms.register_charger(cp)
    await queue.get()


async def create_websocket_server(csms: CentralSystem):
    handler = partial(on_connect, csms=csms)
    ssl = None
    if USE_WSS:
        ssl = ssl_context
    return await websockets.serve(handler, "0.0.0.0", 9000, subprotocols=["ocpp1.6"], ssl = ssl)


async def create_http_server(csms: CentralSystem):
    app = web.Application()
    app.add_routes([web.post("/", change_config)])
    app.add_routes([web.post("/disconnect", disconnect_charger)])

    # Put CSMS in app so it can be accessed from request handlers.
    # https://docs.aiohttp.org/en/stable/faq.html#where-do-i-put-my-database-connection-so-handlers-can-access-it
    app["csms"] = csms

    # https://docs.aiohttp.org/en/stable/web_advanced.html#application-runners
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "localhost", 8080)
    return site


async def main():
    csms = CentralSystem()

    websocket_server = await create_websocket_server(csms)
    http_server = await create_http_server(csms)

    await asyncio.wait([websocket_server.wait_closed(), http_server.start()])


if __name__ == "__main__":
    asyncio.run(main())
