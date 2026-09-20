"""
Classe responsável pelas criação das instâncias dos workers 
"""

import socket
import selectors
import types
import json

from .MatrizResolver import MatrixResolver
from dto.payload import Payload

class WorkerServer:

    def __init__(self, host: str, port: int):
        self.matrix_resolver = MatrixResolver()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((host, port))
        self.sock.setblocking(True)
        print(f"Worker server is listening on host:{self.host}, port:{self.port}")
        self.start_worker()


    def start_worker(self): 
        
        conn, addr = self.sock.accept()

        while True: 
            try:
                msg = self.recieve_message(conn)
                result =  self.matrix_resolver.multiply_column_by_row(conn, msg)
            except:
                break

        conn.close()
        self.sock.close()

    def send_message(conn: socket.socket, payload_msg: Payload):
        data = payload_msg.to_json().encode
        conn.sendall(data)
            
    def recieve_message(connection: socket.socket) -> Payload: 
        #Recebe os 4 primieros bytes que determinam o tamanho do payload enviado
        header = connection.recv(4)
        #Observação: Pelo socket ser bloqueante, não é necessário validar se tem algo disponível para ser consumido no canal antes de chamar o recv()
        length = int.from_bytes(header, 'big')     

        msg_bytes = b""

        while len(msg_bytes) < length:
            chunk = connection.recv(1024)
            if not chunk:
                raise ConnectionResetError()
            msg_bytes += chunk

        return Payload.from_json(json.loads(msg_bytes.decode()))
