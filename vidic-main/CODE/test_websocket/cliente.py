import asyncio
import websockets
import pathlib
import ssl

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
localhost_pem = pathlib.Path(__file__).with_name("localhost.pem")
ssl_context.load_verify_locations(localhost_pem)

async def hola():
    uri = "wss://localhost:8888"
    async with websockets.connect(uri, ssl=ssl_context) as websocket:
        nombre = input('Dime tu nombre:')

        await websocket.send(nombre)
        print(f">>>{nombre}")

        saludo = await websocket.recv()
        print(f"<<< {saludo}")

if __name__ == "__main__":
    asyncio.run(hola())