import socket
import selectors

from .WorkerServer import WorkerServer

HOST = "127.0.0.1"
PORT_WORKER_1 = 30010
PORT_WORKER_2 = 30020
PORT_WORKER_3 = 30030
PORT_WORKER_4 = 30040
PORT_WORKER_5 = 30050


class WorkerConn:
    def __init__(self, sock: socket.socket, id: int):
        self.sock = sock
        self.id = id
        self.is_busy = False

class CordServer: 
    
    def __init__(self):
        self.workers_instance_list = self.initialize_workers()
        self.selector = selectors.DefaultSelector()

    def create_workers(self) -> list[WorkerServer]:

        worker_1 = WorkerServer(HOST, PORT_WORKER_1)
        worker_2 = WorkerServer(HOST, PORT_WORKER_2)
        worker_3 = WorkerServer(HOST, PORT_WORKER_3)
        worker_4 = WorkerServer(HOST, PORT_WORKER_4)
        worker_5 = WorkerServer(HOST, PORT_WORKER_5)

        return [worker_1, worker_2, worker_3, worker_4, worker_5]

    def stabilish_connection_with_workers(self) -> list[WorkerConn]:

        worker_connections = []

        for i, worker in enumerate(self.workers_instance_list): 
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((worker.host, worker.port))
            worker_data = WorkerConn(sock, i)
            self.selector.register(sock, selectors.EVENT_READ, data=worker_data)
            worker_connections.append(sock)
            

            
        