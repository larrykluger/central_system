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

curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"id":""}' \
  http://localhost:8080/disconnect

curl --request GET   http://localhost:8080/id//configuration


Here code of the CSMS with the HTTP API:
"""

import logging
import asyncio
import websockets
from charge_point import ChargePoint
from central_system import CentralSystem
from aiohttp import web
from functools import partial
import ssl
import json
from ocpp.v16.enums import Action, RegistrationStatus
from ocpp.v16 import call_result, call
from colorama import init as colorama_init
from colorama import Fore
from colorama import Style
import pprint

# config
CERT_PATH = "cert/"
USE_WSS = True
CONNECTOR_ID = 1 # The charge point's connector number when it only has one connector.
ID_TAG = "an id tag"
log_level = 7 # 0 - none; 1 - some; 7 - ocpp INFO; 8 - Warning; 9 - Info; 10 - NotSet (all)

if log_level >= 8:
    # set up logging
    if log_level > 0:
        colorama_init()
    if log_level == 7:
        logging.getLogger('ocpp').setLevel(level=logging.INFO)
        logging.getLogger('ocpp').addHandler(logging.StreamHandler())
    match log_level:
        case 8: level = logging.WARNING
        case 9: level = logging.INFO
        case 10: level = logging.NOTSET
        case _: None
    if log_level > 7:
        logging.basicConfig(level=level)

if USE_WSS:
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(CERT_PATH + "fullchain.pem", CERT_PATH + "privkey.pem")

async def home_page(request):
    """ HTTP handler for home_page. """
    return web.Response(text="Hello world!")

async def ping(request):
    """ HTTP handler for ping. """
    return web.Response(text="Pong baby!")

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

async def get_configuration(request):
    """ HTTP handler for getting charger configuration. """
    csms = request.app["csms"]
    if hasattr(request.match_info, 'id'):
        id = request.match_info['id']
    else:
        id = csms.charger_id()
    if not id:
        return web.Response(text="No charger")
    try:
        result = await csms.get_configuration(id)
        # result is <class 'ocpp.v16.call_result.GetConfigurationPayload'>
        response = f"""
<h1>Configuration</h1>
<pre><code>{pprint.pformat(result, indent=4)}</code></pre>
"""
        return web.Response(text=response)
    except ValueError as e:
        print(f"Failed to get configuration: {e}")
        return web.Response(status=404)
    return web.Response()

async def remote_start(request):
    """ HTTP handler for sending remote start. 
    See OCPP docs section 5.11, page 49"""
    csms = request.app["csms"]
    if hasattr(request.match_info, 'id'):
        id = request.match_info['id']
    else:
        id = csms.charger_id()
    if not id:
        return web.Response(text="No charger")
    try:
        result = await csms.remote_start_transaction(id, ID_TAG, CONNECTOR_ID)
        # result is https://github.com/mobilityhouse/ocpp/blob/master/ocpp/v16/schemas/RemoteStartTransactionResponse.json
        response = f"""
<h1>Remote Start Transaction: Response</h1>
<pre><code>{pprint.pformat(result, indent=4)}</code></pre>
"""
        return web.Response(text=response)
    except ValueError as e:
        print(f"Failed to get configuration: {e}")
        return web.Response(status=404)
    return web.Response()


async def on_connect(websocket, path, csms):
    """ For every new charge point that connects, create a ChargePoint instance
    and start listening for messages.
    The ChargePoint is registered at the CSMS.
    """
    charge_point_id = path.strip("/")
    if charge_point_id == "":
        charge_point_id = "none"
    cp = ChargePoint(id=charge_point_id, connection=websocket, log_level=log_level)
    print(f"{Style.BRIGHT}{Fore.GREEN}Charger {cp.id} connected.{Style.RESET_ALL}")

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
    app.add_routes([web.get("/", home_page),
                    web.post("/", change_config),
                    web.post("/disconnect", disconnect_charger),
                    web.get("/cp/{id}/configuration", get_configuration, allow_head=False),
                    web.get("/cp/configuration", get_configuration, allow_head=False),
                    web.get("/cp/{id}/remotestart", remote_start, allow_head=False),
                    web.get("/cp/remotestart", remote_start, allow_head=False),
                    web.get("/ping", ping)])

    # Put CSMS in app so it can be accessed from request handlers.
    # https://docs.aiohttp.org/en/stable/faq.html#where-do-i-put-my-database-connection-so-handlers-can-access-it
    app["csms"] = csms

    # https://docs.aiohttp.org/en/stable/web_advanced.html#application-runners
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, None, 8000) # listen to all sources (don't use "localhost")
    print ("Web server active on 8000")
    await site.start()
    while True:
        await asyncio.sleep(3600)  # sleep forever

async def main():
    csms = CentralSystem()
    await create_websocket_server(csms)
    await create_http_server(csms)

    #ws_task = asyncio.create_task (websocket_server.wait_closed())
    #await asyncio.wait([ws_task])

    #web_task = asyncio.create_task (http_server.start())
    #await asyncio.wait([ws_task, web_task])

if __name__ == "__main__":
    asyncio.run(main())
