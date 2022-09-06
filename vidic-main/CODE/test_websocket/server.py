import asyncio
import websockets
import pathlib
import ssl

async def hola(websocket):
    nombre = await websocket.recv()
    print(f"<<< {nombre}")

    saludo = f"Hola {nombre}"
    await websocket.send(saludo)
    print(saludo)

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
localhost_pem = pathlib.Path(__file__).with_name("localhost.pem")
ssl_context.load_cert_chain(localhost_pem)

async def main():
    print('A la escucha con seguridad.')
    async with websockets.serve(hola, "localhost", 8888):
    # async with websockets.serve(hola, "localhost", 8888, ssl=ssl_context):
        await asyncio.Future()  #run forever

if __name__ == "__main__":
    asyncio.run(main())