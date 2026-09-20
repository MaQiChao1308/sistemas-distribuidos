"""
Parte 2 - Coordenador com middleware (gRPC), comunicação assíncrona.

Cada par (linha, coluna) vira uma chamada remota disparada com .future(), que
devolve na hora. O coordenador preenche a matriz conforme as respostas chegam,
em qualquer ordem.

Os workers precisam estar rodando antes, um por terminal:
    python3 GrpcWorkerServer.py 127.0.0.1 50051   (e 50052, 50053, 50054, 50055)

Depois:
    python3 GrpcCordServer.py [tamanho_da_matriz]
"""

import queue
import random
import sys
import time

from collections import deque

import grpc

from MatrizResolver import MatrixResolver
from dto.payload import Payload

HOST = "127.0.0.1"
WORKER_PORTS = [50051, 50052, 50053, 50054, 50055]

SERVICE_NAME = "matrixmultiplication.MatrixWorker"
METHOD_NAME = "DotProduct"
FULL_METHOD = f"/{SERVICE_NAME}/{METHOD_NAME}"


class RemoteWorker:
    """Canal aberto com um worker e o estado dele."""

    def __init__(self, id: int, port: int, channel: grpc.Channel):
        self.id = id
        self.port = port
        self.channel = channel
        self.is_busy = False

        # Equivale ao stub que o protoc geraria, montado em tempo de execução
        self.dot_product = channel.unary_unary(
            FULL_METHOD,
            request_serializer=lambda body: body.encode(),
            response_deserializer=lambda body: body.decode(),
        )


class GrpcCordServer:

    def __init__(self):
        self.matrix_resolver = MatrixResolver()
        self.remote_workers: list[RemoteWorker] = []

    def connect_to_workers(self, connect_timeout: float = 1.0) -> list[RemoteWorker]:
        """Abre canal com os workers que estiverem no ar e ignora os demais."""

        for i, port in enumerate(WORKER_PORTS):
            channel = grpc.insecure_channel(f"{HOST}:{port}")

            try:
                grpc.channel_ready_future(channel).result(timeout=connect_timeout)
            except grpc.FutureTimeoutError:
                print(f"[GRPC COORD] Worker {i} (porta {port}) indisponível, ignorando")
                channel.close()
                continue

            self.remote_workers.append(RemoteWorker(i, port, channel))

            print(f"[GRPC COORD] Canal aberto com o worker {i} (porta {port})")

        if not self.remote_workers:
            raise RuntimeError(
                "Nenhum worker disponível. Suba pelo menos um antes do coordenador."
            )

        print(f"[GRPC COORD] {len(self.remote_workers)} worker(s) disponível(is)")

        return self.remote_workers

    def coordinate(
        self,
        first_matrix: list[list[int]],
        second_matrix: list[list[int]],
    ) -> list[list[int]]:
        """Valida o par de matrizes, distribui as chamadas e remonta o resultado."""

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

        print(f"[GRPC COORD] {total_tasks} chamadas remotas a distribuir")

        self.connect_to_workers()

        # Faz o papel do selector da Parte 1: é aqui que o coordenador espera
        # por "algum worker terminou"
        completed_calls = queue.Queue()
        received_results = 0

        try:
            self.dispatch_tasks(pending_tasks, completed_calls)

            while received_results < total_tasks:
                worker, finished_call = completed_calls.get()
                answer = Payload.from_json(finished_call.result())

                self.matrix_resolver.build_matrix_result(
                    result_matrix,
                    answer.result,
                    answer.row_id,
                    answer.column_id,
                )

                worker.is_busy = False
                received_results += 1

                print(
                    f"[GRPC COORD] worker {worker.id} devolveu "
                    f"resultado[{answer.row_id}][{answer.column_id}] = {answer.result}"
                )

                self.dispatch_tasks(pending_tasks, completed_calls)
        finally:
            self.shutdown()

        return result_matrix

    def dispatch_tasks(self, pending_tasks: deque, completed_calls: queue.Queue) -> None:
        """Dispara uma chamada para cada worker livre, sem esperar resposta."""

        for worker in self.remote_workers:
            if worker.is_busy or not pending_tasks:
                continue

            task = pending_tasks.popleft()
            worker.is_busy = True

            # .future() volta na hora; o callback avisa quando a resposta chegar
            call = worker.dot_product.future(task.to_json())
            call.add_done_callback(
                lambda finished_call, w=worker: completed_calls.put((w, finished_call))
            )

    def shutdown(self) -> None:
        """Fecha os canais. Os workers seguem no ar aguardando novos clientes."""

        for worker in self.remote_workers:
            worker.channel.close()


def print_matrix(title: str, matrix: list[list[int]]) -> None:
    print(f"\n{title}")

    for row in matrix:
        print("   " + " ".join(f"{value:>5}" for value in row))


if __name__ == "__main__":
    matrix_size = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    # Mesma semente da Parte 1: as duas partes multiplicam as mesmas matrizes
    random.seed(42)

    first_matrix = [
        [random.randint(1, 9) for _ in range(matrix_size)]
        for _ in range(matrix_size)
    ]
    second_matrix = [
        [random.randint(1, 9) for _ in range(matrix_size)]
        for _ in range(matrix_size)
    ]

    coordinator = GrpcCordServer()

    print_matrix("[GRPC COORD] Primeira matriz:", first_matrix)
    print_matrix("[GRPC COORD] Segunda matriz:", second_matrix)
    print()

    started_at = time.time()
    result = coordinator.coordinate(first_matrix, second_matrix)
    elapsed = time.time() - started_at

    print_matrix("[GRPC COORD] Matriz resultado:", result)

    print(f"\n[GRPC COORD] Concluído em {elapsed:.3f}s")
