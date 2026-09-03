# Caio Lopes e Ma Qi

import socket
import time

# Função principal do cliente
def start_client():
    server_address = '127.0.0.1'
    server_port = 8000

    # Criação do socket TCP e conexão com o servidor
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((server_address, server_port))
        print("[INFO] Conectado ao servidor.")

        # Envia 10 mensagens para o servidor
        for i in range(1, 11):
            message = f"Pedido de Servico {i}"
            client_socket.send(message.encode())
            
            # Aguarda resposta do servidor
            data = client_socket.recv(40).decode()
            print(f"Recebido: {data}")
            
            # Espera 2 segundos antes de enviar o próximo pedido
            time.sleep(2)

# Início da execução
if __name__ == "__main__":
    start_client()