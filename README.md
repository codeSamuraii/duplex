# Duplex
Python [asyncio](https://docs.python.org/3/library/asyncio.html) module to easily create a socket communication channel with a [queue](https://docs.python.org/3/library/asyncio-queue.html) API.

Just wait for messages in the inbox/receive queue or place outgoing data in the send queue.

### Usage
Listen as a server :
```python
duplex, recv_queue, send_queue = Duplex.new()
host, port = await duplex.listen(port=8888)
print(f"Incoming connection from {host}:{port} !")
```

Connect as a client :
```python
duplex, recv_queue, send_queue = Duplex.new()
host, port = await duplex.connect(host='127.0.0.1', port=8888)
print(f"Connected to {host}:{port} !")
```

Once connected, you can exchange message with the returned queues :
```python
await send_queue.put(b'Hi !')
msg = await recv_queue.get()
```

You can provide existing queue objects to be used in `Duplex.new()`. Otherwise, they will be created.

Of course, we can automate all that asynchronously with `asyncio`:
```python
async def get_and_print(recv_queue):
    """Get messages from the inbox and print them."""
    while True:
        msg = await recv_queue.get()
        if msg is None:
            break
        print(f"Received: {msg}")

async def random_send(send_queue):
    """Sends messages with a random delay."""
    for i in range(100):
        await asyncio.sleep(random.random())
        await send_queue.put(f"Hello #{i}".encode())   

async def main():
    duplex, recv_queue, send_queue = Duplex.new()
    host, port = await duplex.connect(host='127.0.0.1', port=8888)
    print(f"Connected to {host}:{port}.")
    
    tasks = {
        asyncio.create_task(get_and_print(recv_queue)),
        asyncio.create_task(random_send(send_queue))
    }

    await duplex.disconnected
    print("Disconnected.")
```

The `duplex.disconnected` future can be awaited to execute until connection is closed or interrupted.
In that situation, the inbox/receive queue will get a `None` item to notify consumers should return.

Similarly, `await duplex.connected` / `duplex.is_running()` can be used to wait for a connection to be established.

Other methods:
- `await duplex.closing()` / `duplex.close()`,
- `await duplex.aborting()` / `duplex.abort()`.
