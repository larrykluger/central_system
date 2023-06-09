import asyncio
from websockets.server import serve
import ssl

import logging
logging.basicConfig(level=logging.NOTSET) # DEBUG)

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain("cert.pem", "cert.pem")



async def echo(websocket):
    async for message in websocket:
        print(message)

async def main():
    async with serve(echo, "", 9000, ssl=ssl_context):
        await asyncio.Future()  # run forever

asyncio.run(main())
