from tools import *
eventlet_routine()

import asyncio
import eventlet
from duplex import Duplex


def print_message(msg):
    print(f">>> {msg}")

async def wait_for_messages(duplex: Duplex, callback: callable):
    while True:
        print("[SERVER] Waiting for message...")
        msg = await duplex.wait_for_message()

        if msg:
            callback(msg)
        elif not msg:
            print("[SERVER] No message received.")
            break
        elif msg == b"STOP":
            print("[SERVER] Received stop message.")
            break

        await asyncio.sleep(0.2)

    print(f"[SERVER] Closing.")

async def main():
    print("[SERVER] Starting server...")
    duplex = await Duplex.listen_wait()

    job = asyncio.create_task(wait_for_messages(duplex, print_message))
    res = await asyncio.gather(job, return_exceptions=True)
    print(f'------\n[SERVER] Result: {res}\n-----')


if __name__ == "__main__":
    asyncio.run(main())