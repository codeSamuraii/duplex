import re
import socket
import logging
import eventlet

from tools import *

log = configure_logging('Duplex')


class DuplexAPI:
    def __new__(cls):
        eventlet_routine()
        return object.__new__(cls)

    def __init__(self):
        self._job = None
        self._sock = None
        self._regex = None
        self._running = None
        self._last_exc = None
        self._buffer = bytearray()
    
        self._pool = eventlet.GreenPool()
        self._recv_queue = eventlet.Queue()
        self._send_queue = eventlet.Queue()

        if type(self) is DuplexAPI:
            raise NotImplementedError("DuplexAPI is not meant to be instanciated, use the Duplex class.")

    def _pack_msg(self, msg: bytes):
        return b'%START%' + msg + b'%STOP%'

    def _unpack_msg(self, data: bytes):
        if self._regex is None:
            self._regex = re.compile(b'%START%(.*?)%STOP%', flags=re.DOTALL)

        messages = self._regex.findall(data)
        remainder = self._regex.sub(b'', data)
        return messages, remainder
    
    def _reset_buffer(self, data: bytes):
        self._buffer.clear()
        self._buffer.extend(data)
    
    def _recv_to_buffer(self):
        while True:
            try:
                chunk = self._sock.recv(4096)
            except socket.error:
                # Non-blocking socket, no data available.
                break

            if chunk:
                self._buffer.extend(chunk)
            else:
                self._notify_disconnected()
                break

    def _recv_msg(self):
        self._recv_to_buffer()
        messages, remainder = self._unpack_msg(self._buffer)
        self._reset_buffer(remainder)
        return messages
    
    def _send_msg(self, msg: bytes):
        packet = self._pack_msg(msg)
        self._sock.sendall(packet)

    def _send_items_in_queue(self):
        if not self._send_queue.empty():
            try:
                packet = self._send_queue.get(timeout=2)
            except eventlet.queue.Empty:
                log.warning("Couldn't fetch item from queue.")
            else:
                self._send_msg(packet)
                
    def _receive_and_put_in_queue(self):
        for msg in self._recv_msg():
            try:
                self._recv_queue.put(msg, timeout=2)
            except eventlet.queue.Full:
                log.warning(f"Couldn't put item in queue.")
    
    def _loop_running(self):
        return self._running is True

    def _stop_loop(self):
        self._running = False
    
    def _exchange_messages(self):
        while self._loop_running():
            self._send_items_in_queue()
            self._receive_and_put_in_queue()
            eventlet.sleep()
    
    def _notify_disconnected(self):
        log.debug("Peer disconnected.")
        self.stop(exception=socket.error("Other side disconnected."))
    
    def _kill_job(self):
        if self._job is not None:
            self._job.kill()
        if self._sock is not None:
            self._sock.close()
    
    def _handle_exception(self, raise_exc: bool = True):
        if self._last_exc is None:
            return
        
        last_exc = self._last_exc
        
        if raise_exc:
            self._last_exc = None
            raise last_exc
        else:
            log.exception("Duplex stopped due to an exception.", exc_info=last_exc)
    
    def _get(self, block: bool = True, timeout: int | None = None):
        msg = self._recv_queue.get(block=block, timeout=timeout)
        return msg
    
    def _get_safe(self):
        while True:
            try:
                msg = self._get(block=False, timeout=1)
                return msg
            except eventlet.queue.Empty:
                pass
            
            if not self._loop_running():
                log.error("Can't receive message, duplex interrupted.")
                return b''
            
            eventlet.sleep()
    
    def _put(self, *args, **kwargs):
        self._send_queue.put(*args, **kwargs)
    
    def __del__(self):
        self.close(raise_exc=False)


class Duplex(DuplexAPI):
    
    def listen(self, port: int, *, host: str):
        """Wait for a connection on the given port and host."""
        server = socket.create_server((host, port))
        server.listen(0)
        log.info(f"Listening on %s:%d.", host, port)

        self._sock, peer = server.accept()
        self._sock.setblocking(False)
        log.info(f"Connection from %s accepted.", peer[0])
    
    def connect(self, host: str, port: int):
        """Connect to the given host and port."""
        self._sock = socket.create_connection((host, port))
        self._sock.setblocking(False)
        log.info(f"Connected to %s:%d.", host, port)
    
    def start(self):
        """Start the message exchange loop."""
        self._running = True
        self._job = self._pool.spawn(self._exchange_messages)
        log.debug("Message exchange job started.")
    
    def stop(self, exception: Exception | None = None):
        """Stop the message exchange loop."""
        if self._loop_running():
            self._stop_loop()
            log.debug("Message exchange loop stopped.")

        if exception is not None:
            self._last_exc = exception
    
    def close(self, raise_exc: bool = True):
        """Wait for everything to be closed, raise an exception if there was an error by default."""
        if self._loop_running():
            self.stop()

        self._kill_job()
        self._pool.waitall()
        self._handle_exception(raise_exc)

    def receive(self, timeout: int | None = None):
        """
        Wait for an incoming message.
        If `timeout` is 0, return directly with a message if available or raise `eventlet.queue.Empty`.
        If `timeout` is a positive integer, wait that many seconds for a message, before raising `eventlet.queue.Empty`.
        If `timeout` is None or not specified, block until a message is received. This method *will* return early in case of error.
        """
        if not self._loop_running():
            self.close()
    
        if timeout is None:
            return self._get_safe()
        return self._get(block=True, timeout=timeout)
    
    def send(self, msg: bytes, notify_cb: callable = None):
        """Put a message in the send queue."""
        if not self._loop_running():
            self.close()
        
        self._put(msg)
    
    def set_logging_level(self, level: int):
        log.setLevel(level)

    @classmethod
    def connect_to(cls, host: str = '127.0.0.1', port: int = 8765, verbose: bool = False):
        """Create a Duplex client connected to the given host and port."""
        duplex = cls()
        if verbose: duplex.set_logging_level(logging.DEBUG)
        duplex.connect(host, port)
        duplex.start()
        return duplex
    
    @classmethod
    def listen_on(cls, host: str = '0.0.0.0', port: int = 8765, verbose: bool = False):
        """Create a Duplex server listening on the given host and port."""
        duplex = cls()
        if verbose: duplex.set_logging_level(logging.DEBUG)
        duplex.listen(port, host=host)
        duplex.start()
        return duplex
    

    @classmethod
    @make_awaitable
    def listen_wait(cls, host: str = '0.0.0.0', port: int = 8765, verbose: bool = False):
        """Create a Duplex server and wait for a connection on given host and port."""
        return cls.listen_on(host, port, verbose)

    @make_awaitable
    def wait_for_message(self, timeout: int | None = None):
        """
        Wait for an incoming message.
        If `timeout` is 0, return directly with a message if available or raise `eventlet.queue.Empty`.
        If `timeout` is a positive integer, wait that many seconds for a message, before raising `eventlet.queue.Empty`.
        If `timeout` is None or not specified, block until a message is received. This method *will* still return early in case of error.
        """
        return self.receive(timeout=timeout)

