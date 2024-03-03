import eventlet
from duplex import Duplex
from tools import *
eventlet_routine()


def main():
    duplex = Duplex.connect_to()
    duplex.send(b"Just connected to you client !")
    i = 0
    
    while True:
        try:
            msg = duplex.receive(1)
            if msg:
                print(f"[CLIENT] Received: {msg.decode()}")
        except eventlet.queue.Empty as e:
            pass

        msg = f"Hello {i} from client."
        duplex.send(msg.encode())
        print("[CLIENT] Sent: ", msg)

        if i > 6:
            print("[CLIENT] Closing...")
            duplex.close()
            eventlet.sleep()
            print("[CLIENT] Closed.")
            break

        i += 1
        eventlet.sleep()

    print("[CLIENT] Done.")


if __name__ == "__main__":
    main()