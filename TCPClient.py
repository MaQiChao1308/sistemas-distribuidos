# Caio Lopes e Ma Qi

import socket

def start_client():
    server_address = '127.0.0.1'
    server_port = 8000

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((server_address, server_port))
        print("[INFO] Conectado ao servidor da Calculadora.")
        print("Digite uma operação matemática (ex: 2 + 2, 10 * 5) ou 'sair' para encerrar.\n")

        while True:
            # Lê a entrada do usuário
            message = input("Sua conta: ")
            
            if message.lower() == 'sair':
                print("Encerrando cliente...")
                break
                
            if message.strip() == "":
                continue

            # Envia a conta para o servidor
            client_socket.send(message.encode())
            
            # Aguarda a resposta (o resultado do cálculo)
            data = client_socket.recv(1024).decode()
            print(f"Servidor diz: {data}\n")

if __name__ == "__main__":
    start_client()