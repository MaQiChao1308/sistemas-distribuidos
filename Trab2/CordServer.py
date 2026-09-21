"""
Coordenador: distribui os pares (linha, coluna) entre os workers e
remonta a matriz resultado conforme as respostas chegam.

Os workers precisam estar rodando antes, um por terminal:
    python3 WorkerServer.py 127.0.0.1 30010    (e 30020, 30030, 30040, 30050)

Depois:
    python3 CordServer.py

Não é obrigatório ter os cinco de pé: o coordenador usa os que encontrar,
desde que haja pelo menos um.
"""

import random
import socket
import selectors
import sys
import time

from collections import deque

from MatrizResolver import MatrixResolver
from dto.payload import Payload

HOST = "127.0.0.1"
PORT_WORKER_1 = 30010
PORT_WORKER_2 = 30020
PORT_WORKER_3 = 30030
PORT_WORKER_4 = 30040
PORT_WORKER_5 = 30050

WORKER_PORTS = [
    PORT_WORKER_1,
    PORT_WORKER_2,
    PORT_WORKER_3,
    PORT_WORKER_4,
    PORT_WORKER_5,
]

MATRIX_SIZE = 10

# Semente fixa: as mesmas matrizes em toda execução, para comparar os tempos
# entre a versão síncrona e a assíncrona sem mudar a carga de trabalho
random.seed(42)

FIRST_MATRIX = [
    [random.randint(1, 9) for _ in range(MATRIX_SIZE)]
    for _ in range(MATRIX_SIZE)
]
SECOND_MATRIX = [
    [random.randint(1, 9) for _ in range(MATRIX_SIZE)]
    for _ in range(MATRIX_SIZE)
]

class WorkerConn:
    def __init__(self, sock: socket.socket, id: int):
        self.sock = sock
        self.id = id
        self.is_busy = False

class CordServer:

    def __init__(self):
        self.selector = selectors.DefaultSelector()
        self.matrix_resolver = MatrixResolver()
        self.worker_connections: list[WorkerConn] = []

    def stabilish_connection_with_workers(self, connect_timeout: float = 0.5) -> list[WorkerConn]:
        """
            Conecta nos workers que estiverem de pé e registra cada socket no selector.
            Porta sem ninguém escutando é apenas ignorada: o coordenador distribui
            o trabalho entre a quantidade de workers que encontrar.
        """

        for i, port in enumerate(WORKER_PORTS):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(connect_timeout)

            try:
                sock.connect((HOST, port))
            except OSError as error:
                print(f"[COORD] Worker {i} (porta {port}) indisponível, ignorando: {error}")
                sock.close()
                continue

            # O timeout valia só para o connect: volta ao modo bloqueante,
            # que é o que o receive_message espera
            sock.settimeout(None)

            worker_data = WorkerConn(sock, i)

            self.selector.register(sock, selectors.EVENT_READ, data=worker_data)
            self.worker_connections.append(worker_data)

            print(f"[COORD] Conectado ao worker {i} (porta {port})")

        if not self.worker_connections:
            raise RuntimeError(
                "Nenhum worker disponível. Suba pelo menos um antes do coordenador."
            )

        print(f"[COORD] {len(self.worker_connections)} worker(s) disponível(is)")

        return self.worker_connections

    def coordinate(
        self,
        first_matrix: list[list[int]],
        second_matrix: list[list[int]],
        mode: str = "async",
    ) -> list[list[int]]:
        """
            Valida o par de matrizes e coordena a distribuição em modo 'async' ou 'sync'.
        """
        if mode == "sync":
            return self.coordinate_sync(first_matrix, second_matrix)
        return self.coordinate_async(first_matrix, second_matrix)

    def coordinate_async(
        self,
        first_matrix: list[list[int]],
        second_matrix: list[list[int]],
    ) -> list[list[int]]:
        """
            Comunicação assíncrona: distribui tarefas aos workers livres e coleta
            as respostas usando multiplexação I/O (selector) conforme chegam.
        """

        if not self.matrix_resolver.validating_the_matrix_pair(first_matrix, second_matrix):
            raise ValueError(
                "Operação impossível: o número de colunas da primeira matriz "
                "é diferente do número de linhas da segunda"
            )

        pending_tasks = deque(
            self.matrix_resolver.build_rows_and_colums_pairs(first_matrix, second_matrix)
        )
        total_tasks = len(pending_tasks)

        result_matrix = [
            [None for _ in range(len(second_matrix[0]))]
            for _ in range(len(first_matrix))
        ]

        print(f"[COORD ASYNC] {total_tasks} pares (linha, coluna) a distribuir assincronamente")

        self.stabilish_connection_with_workers()

        received_results = 0

        try:
            self.dispatch_tasks(pending_tasks)

            while received_results < total_tasks:
                # Devolve apenas os workers que já têm resposta pronta para leitura
                for key, _ in self.selector.select():
                    worker = key.data
                    answer = self.receive_message(worker.sock)

                    self.matrix_resolver.build_matrix_result(
                        result_matrix,
                        answer.result,
                        answer.row_id,
                        answer.column_id,
                    )

                    worker.is_busy = False
                    received_results += 1

                    print(
                        f"[COORD ASYNC] worker {worker.id} devolveu "
                        f"resultado[{answer.row_id}][{answer.column_id}] = {answer.result}"
                    )

                # Workers que acabaram de liberar já recebem o próximo par
                self.dispatch_tasks(pending_tasks)
        finally:
            self.shutdown()

        return result_matrix

    def coordinate_sync(
        self,
        first_matrix: list[list[int]],
        second_matrix: list[list[int]],
    ) -> list[list[int]]:
        """
            Comunicação síncrona: despacha uma tarefa por vez e aguarda a resposta
            daquele trabalhador de forma bloqueante antes de prosseguir com o próximo par.
        """

        if not self.matrix_resolver.validating_the_matrix_pair(first_matrix, second_matrix):
            raise ValueError(
                "Operação impossível: o número de colunas da primeira matriz "
                "é diferente do número de linhas da segunda"
            )

        pending_tasks = deque(
            self.matrix_resolver.build_rows_and_colums_pairs(first_matrix, second_matrix)
        )
        total_tasks = len(pending_tasks)

        result_matrix = [
            [None for _ in range(len(second_matrix[0]))]
            for _ in range(len(first_matrix))
        ]

        print(f"[COORD SYNC] {total_tasks} pares (linha, coluna) a distribuir sequencialmente")

        self.stabilish_connection_with_workers()

        num_workers = len(self.worker_connections)
        worker_idx = 0

        try:
            while pending_tasks:
                task = pending_tasks.popleft()
                worker = self.worker_connections[worker_idx % num_workers]
                worker_idx += 1

                # Envia e bloqueia no recv esperando a resposta antes de enviar o próximo
                self.send_message(worker.sock, task)
                answer = self.receive_message(worker.sock)

                self.matrix_resolver.build_matrix_result(
                    result_matrix,
                    answer.result,
                    answer.row_id,
                    answer.column_id,
                )

                print(
                    f"[COORD SYNC] worker {worker.id} devolveu "
                    f"resultado[{answer.row_id}][{answer.column_id}] = {answer.result}"
                )
        finally:
            self.shutdown()

        return result_matrix

    def dispatch_tasks(self, pending_tasks: deque) -> None:
        """Entrega um par para cada worker livre, enquanto houver fila."""

        for worker in self.worker_connections:
            if worker.is_busy or not pending_tasks:
                continue

            task = pending_tasks.popleft()

            worker.is_busy = True

            self.send_message(worker.sock, task)

    def shutdown(self) -> None:
        """Fecha as conexões com os workers e encerra o selector."""

        for worker in self.worker_connections:
            try:
                self.selector.unregister(worker.sock)
            except Exception:
                pass
            try:
                worker.sock.close()
            except Exception:
                pass

        self.worker_connections = []
        try:
            self.selector.close()
        except Exception:
            pass

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


if __name__ == "__main__":
    mode = "async"
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("sync", "async", "compare"):
        mode = sys.argv[1].lower()

    if mode == "compare":
        print("=== 1. EXECUTANDO MODO SÍNCRONO ===")
        coord_sync = CordServer()
        started_at = time.time()
        result_sync = coord_sync.coordinate(FIRST_MATRIX, SECOND_MATRIX, mode="sync")
        elapsed_sync = time.time() - started_at
        print(f"\n[COORD] Modo SYNC concluído em {elapsed_sync:.4f}s")

        print("\n=== 2. EXECUTANDO MODO ASSÍNCRONO ===")
        coord_async = CordServer()
        started_at = time.time()
        result_async = coord_async.coordinate(FIRST_MATRIX, SECOND_MATRIX, mode="async")
        elapsed_async = time.time() - started_at
        print(f"\n[COORD] Modo ASYNC concluído em {elapsed_async:.4f}s")

        print("\n" + "=" * 45)
        print("RESULTADO COMPARATIVO (Sockets TCP)")
        print("=" * 45)
        print(f"Tempo Síncrono:   {elapsed_sync:.4f}s")
        print(f"Tempo Assíncrono: {elapsed_async:.4f}s")
        speedup = (elapsed_sync / elapsed_async) if elapsed_async > 0 else 0
        print(f"Speedup Assíncrono: {speedup:.2f}x mais rápido")
        print("=" * 45)
    else:
        coordinator = CordServer()
        started_at = time.time()
        result = coordinator.coordinate(FIRST_MATRIX, SECOND_MATRIX, mode=mode)
        elapsed = time.time() - started_at

        print(f"\n[COORD] Matriz resultado ({mode.upper()}):")
        for row in result:
            print("  ", row)

        print(f"\n[COORD] Modo {mode.upper()} concluído em {elapsed:.4f}s")
