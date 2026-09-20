import socket
import selectors

from .WorkerServer import WorkerServer
from dto.payload import Payload

HOST = "127.0.0.1"
PORT_WORKER_1 = 30010
PORT_WORKER_2 = 30020
PORT_WORKER_3 = 30030
PORT_WORKER_4 = 30040
PORT_WORKER_5 = 30050


FIRST_MATRIX = [[1,2],[3,4]]
SECOND_MATRIX = [[5,6],[7,8]]

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

        return worker_connections
    
    def send_message(self, connection: socket.socket, payload_msg: Payload) -> None:
        """Envia [4 bytes de tamanho][JSON] para o worker."""

        body = payload_msg.to_json().encode()
        header = len(body).to_bytes(4, 'big')

        connection.sendall(header + body)

    def receive_exact(self, connection: socket.socket, size: int) -> bytes:
        """
            Lê exatamente `size` bytes do canal.
            Pedir sempre o que falta (e não um valor fixo) evita consumir
            bytes da próxima mensagem que já estejam no buffer do socket.
        """

        buffer = b""

        while len(buffer) < size:
            chunk = connection.recv(size - len(buffer))

            if not chunk:
                raise ConnectionResetError(f"Worker fechou a conexão")

            buffer += chunk

        return buffer

    def receive_message(self, connection: socket.socket) -> Payload:
        """
            Lê uma resposta completa do worker.
            Observação: só chamar depois que o selector sinalizou EVENT_READ
            nesse socket. Como os sockets são bloqueantes, se for chamado sem
            dados disponíveis o coordenador trava até o worker responder.
        """

        # Os 4 primeiros bytes determinam o tamanho do payload enviado
        header = self.receive_exact(connection, 4)
        length = int.from_bytes(header, 'big')

        body = self.receive_exact(connection, length)

        return Payload.from_json(body.decode())
