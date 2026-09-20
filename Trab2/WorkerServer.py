"""
Classe responsável pelas criação das instâncias dos workers

Executado como processo independente:
    python3 WorkerServer.py <host> <porta>
"""

import socket
import sys

from MatrizResolver import MatrixResolver
from dto.payload import Payload

class WorkerServer:

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.matrix_resolver = MatrixResolver()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Permite reusar a porta logo após um encerramento, sem esperar o TIME_WAIT
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(1)
        self.sock.setblocking(True)

        print(f"Worker server is listening on host:{self.host}, port:{self.port}")


    def start_worker(self):

        # Bloqueia até o coordenador conectar
        conn, addr = self.sock.accept()
        print(f"[WORKER {self.port}] Coordenador conectado: {addr}")

        try:
            while True:
                payload = self.receive_message(conn)

                payload.result = self.matrix_resolver.multiply_column_by_row(payload)
                print(
                    f"[WORKER {self.port}] linha {payload.row_id} x coluna {payload.column_id}"
                    f" = {payload.result}"
                )

                self.send_message(conn, payload)
        except ConnectionResetError as error:
            print(f"[WORKER {self.port}] Encerrando: {error}")
        finally:
            conn.close()
            self.sock.close()

    def send_message(self, connection: socket.socket, payload_msg: Payload) -> None:
        """Envia [4 bytes de tamanho][JSON] para o coordenador."""

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
                raise ConnectionResetError("Coordenador fechou a conexão")

            buffer += chunk

        return buffer

    def receive_message(self, connection: socket.socket) -> Payload:
        # Os 4 primeiros bytes determinam o tamanho do payload enviado
        # Observação: Pelo socket ser bloqueante, não é necessário validar se tem algo
        # disponível para ser consumido no canal antes de chamar o recv()
        header = self.receive_exact(connection, 4)
        length = int.from_bytes(header, 'big')

        body = self.receive_exact(connection, length)

        return Payload.from_json(body.decode())


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 30010

    WorkerServer(host, port).start_worker()
