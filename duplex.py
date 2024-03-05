import asyncio
import logging

log = logging.getLogger('Duplex')


class DuplexProtocol(asyncio.Protocol):

    def __init__(self, inbox: asyncio.Queue):
        self.inbox = inbox
        self.transport = None

        self.connected = asyncio.Future()
        self.disconnected = asyncio.Future()
    
    async def get_transport(self):
        await self.connected
        return self.transport

    def connection_made(self, transport):
        self.transport = transport
        self.connected.set_result(transport.get_extra_info('peername'))
    
    def data_received(self, data):
        self.inbox.put_nowait(data)

    def eof_received(self):
        self.inbox.put_nowait(None)
        self.transport.close()
    
    def connection_lost(self, exception):
        if self.disconnected.done():
            return

        if not self.transport.is_closing():
            self.transport.close()
    
        if exception is not None:
            self.disconnected.set_exception(exception)
        else:
            self.disconnected.set_result(None)


class Duplex:
    def __init__(self, inbox: asyncio.Queue, outbox: asyncio.Queue, *args):
        self.inbox = inbox
        self.outbox = outbox
        self.transport = None
        self.protocol = None
        self.send_job = None

        if ... not in args:
            raise NotImplementedError("Duplex should be instanciated with `new()`.")
    
    @property
    def connected(self):
        """Resolves with (host, port) when the connection is established."""
        return self.protocol.connected
    
    @property
    def disconnected(self):
        """Resolves when the connection is closed or lost. Raises if an error occurred."""
        return self.protocol.disconnected
    
    def is_running(self):
        """Check if connected and exchanging data."""
        started = self.protocol.connected.done() and self.transport is not None
        ended = self.protocol.disconnected.done() or self.transport.is_closing()
        return started and not ended

    def close(self):
        """Close the connection."""
        self.transport.close()
    
    async def closing(self):
        """Wait for the connection to close."""
        self.close()
        return await self.disconnected
    
    def abort(self):
        """Interrupt the connection without notifying or cleaning up."""
        self.transport.abort()

    async def aborting(self):
        """Wait for the connection to be interrupted."""
        self.abort()
        return await self.disconnected 

    async def _send_job(self):
        await self.connected
        try:
            await self._send_loop()
        except Exception as e:
            log.error(e)
            self.protocol.disconnected.set_exception(e)

    async def _send_loop(self):
        await self.connected
        while self.is_running():
            data = await self.outbox.get()
            self.transport.write(data)

    @classmethod
    def new(cls, inbox: asyncio.Queue | None = None, outbox: asyncio.Queue | None = None):
        """
        Create a new Duplex instance.
        Will use provided queues or create new ones if not provided.
        """
        recv_queue = inbox or asyncio.Queue()
        send_queue = outbox or asyncio.Queue()
        duplex = cls(recv_queue, send_queue, ...)
        return duplex, duplex.inbox, duplex.outbox
    
    async def connect(self, host: str = '127.0.0.1', port: int = 8765):
        """Connect to a Duplex server."""
        self.protocol = DuplexProtocol(self.inbox)
        loop = asyncio.get_running_loop()

        self.transport, _ = await loop.create_connection(lambda: self.protocol, host, port)

        self.send_job = loop.create_task(self._send_job())
        return await self.connected
    
    async def listen(self, host: str = '0.0.0.0', port: int = 8765):
        """Listen for incoming connections."""
        self.protocol = DuplexProtocol(self.inbox)
        loop = asyncio.get_running_loop()

        await loop.create_server(lambda: self.protocol, host, port)
        self.transport = await self.protocol.get_transport()

        self.send_job = loop.create_task(self._send_job())
        return await self.connected