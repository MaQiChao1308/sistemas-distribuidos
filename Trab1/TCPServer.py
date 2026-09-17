# Caio Lopes e Ma Qi

import socket
import threading

class ClientThread(threading.Thread):
    def __init__(self, client_socket, address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.address = address
        print(f"[INFO] Conectado a {address}")

    def run(self):
        try:
            while True:
                # 1024 bytes de buffer (padrão comum)
                data = self.client_socket.recv(1024).decode().strip()
                if not data:
                    break
                print(f"[{self.address[1]}] Recebeu a conta: {data}")
                
                try:
                    # O eval() executa a string como se fosse código Python (ex: "2+2" vira 4)
                    resultado = str(eval(data))
                    response = f"Resultado: {resultado}"
                except ZeroDivisionError:
                    response = "Erro: Impossível dividir por zero!"
                except Exception:
                    response = "Erro: Expressão matemática inválida."
                
                # Envia a resposta calculada de volta ao cliente
                self.client_socket.send(response.encode())
        except Exception as e:
            print(f"[ERRO] {e}")
        finally:
            self.client_socket.close()
            print(f"[INFO] Conexão com {self.address} encerrada.")

def start_server():
    server_port = 8000
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', server_port))
    server_socket.listen()

    print(f"[INFO] Servidor Calculadora escutando na porta {server_port}...")

    while True:
        client_socket, addr = server_socket.accept()
        thread = ClientThread(client_socket, addr)
        thread.start()

if __name__ == "__main__":
    start_server()