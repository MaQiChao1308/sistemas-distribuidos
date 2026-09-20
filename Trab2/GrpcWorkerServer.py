"""
Parte 2 - Worker com middleware (gRPC).

Publica o método remoto DotProduct. O corpo da mensagem é o mesmo JSON do
Payload usado na Parte 1, então não há .proto nem código gerado: o método é
registrado em tempo de execução pela API genérica do gRPC.

    python3 GrpcWorkerServer.py <host> <porta>
"""

import sys

from concurrent import futures

import grpc

from MatrizResolver import MatrixResolver
from dto.payload import Payload

SERVICE_NAME = "matrixmultiplication.MatrixWorker"
METHOD_NAME = "DotProduct"


class GrpcWorkerServer:

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.matrix_resolver = MatrixResolver()
        self.served_requests = 0

    def dot_product(self, request: str, context) -> str:
        """Método remoto: recebe o Payload em JSON e devolve com o result preenchido."""

        payload = Payload.from_json(request)
        payload.result = self.matrix_resolver.multiply_column_by_row(payload)

        self.served_requests += 1

        # flush=True: a linha aparece na hora, mesmo com a saída redirecionada
        print(
            f"[GRPC WORKER {self.port}] linha {payload.row_id} x coluna {payload.column_id}"
            f" = {payload.result}  (chamadas atendidas: {self.served_requests})",
            flush=True,
        )

        return payload.to_json()

    def build_server(self) -> grpc.Server:
        # max_workers=1: uma chamada por vez, igual ao worker da Parte 1
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))

        handler = grpc.method_handlers_generic_handler(SERVICE_NAME, {
            METHOD_NAME: grpc.unary_unary_rpc_method_handler(
                self.dot_product,
                request_deserializer=lambda body: body.decode(),
                response_serializer=lambda body: body.encode(),
            )
        })

        server.add_generic_rpc_handlers((handler,))
        server.add_insecure_port(f"{self.host}:{self.port}")

        return server

    def start_worker(self) -> None:
        server = self.build_server()
        server.start()

        print(f"[GRPC WORKER {self.port}] {SERVICE_NAME} publicado em {self.host}:{self.port}")

        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            print(f"\n[GRPC WORKER {self.port}] Encerrando")
            server.stop(grace=None)


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 50051

    GrpcWorkerServer(host, port).start_worker()
