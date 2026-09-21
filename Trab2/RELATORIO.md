# Relatório Técnico — Multiplicação Distribuída de Matrizes

**Disciplina:** Sistemas Distribuídos · **Autor:** *(preencher)* · **Data:** setembro de 2026

---

## 1. Arquitetura (mestre/escravo)

Um processo **coordenador** (mestre) conhece as duas matrizes e não calcula nada; cinco processos
**trabalhadores** (escravos) calculam e não sabem que existe uma matriz.

A unidade de trabalho é o par *(linha i de A, coluna j de B)*: para matrizes `n × p` são geradas
`n × p` tarefas independentes, mantidas numa fila (`deque`) no coordenador. Cada tarefa carrega os
índices `row_id` e `column_id` além dos dois vetores, e o trabalhador devolve esses índices junto do
resultado. É esse eco que permite escrever o valor na célula correta **sem depender da ordem de
chegada** das respostas.

```
          fila de n×p pares
                 |
   +-------------v-------------+   distribui par  -> worker livre
   |        COORDENADOR        |   recebe result. -> preenche C[i][j]
   +--+-------+-------+-------++
      |       |       |       |
   worker0 worker1 worker2 ... (produto escalar)
```

Não há divisão prévia do trabalho: cada trabalhador recebe uma tarefa por vez e, ao responder,
recebe a próxima da fila. O balanceamento é consequência disso — quem termina antes processa mais.
Numa execução 10 × 10 com cinco trabalhadores a divisão observada foi 21/21/20/20/18 tarefas, sem
nenhum cálculo de partição. O coordenador também tolera número variável de trabalhadores: portas
sem ninguém escutando são ignoradas e a execução segue com os que responderem.

| Arquivo | Responsabilidade | Usado por |
|---|---|---|
| `MatrizResolver.py` | Validação do par, produto escalar, geração dos pares, montagem do resultado | Partes 1 e 2 |
| `dto/payload.py` | DTO `Payload` e serialização JSON | Partes 1 e 2 |
| `WorkerServer.py` / `CordServer.py` | Comunicação direta por sockets TCP | Parte 1 |
| `GrpcWorkerServer.py` / `GrpcCordServer.py` | Comunicação via middleware gRPC | Parte 2 |

As duas primeiras linhas são o ponto central da modularização: **a lógica da multiplicação foi
escrita uma única vez**. Trocar comunicação direta por middleware não alterou nenhuma linha de
regra de negócio.

---

## 2. Parte 1 — Comunicação direta (sockets TCP)

### 2.1 Protocolo

TCP entrega um fluxo de bytes, não mensagens: um `recv()` pode devolver metade de um envio ou dois
envios grudados. Foi preciso criar um enquadramento próprio:

```
[ 4 bytes: tamanho do corpo, big-endian ][ corpo: JSON do Payload ]
```

O `big-endian` é a convenção de rede. A leitura usa `receive_exact(conn, n)`, que chama
`recv(n - len(buffer))` em laço até completar exatamente `n` bytes — pedir o que falta evita
consumir bytes da mensagem seguinte.

### 2.2 Comunicação assíncrona

O coordenador mantém uma conexão aberta por trabalhador, todas registradas no `selectors`. O laço
distribui para os livres, dorme até alguém responder, processa e redistribui:

```python
self.dispatch_tasks(pending_tasks)
while received_results < total_tasks:
    for key, _ in self.selector.select():      # acorda só com quem tem resposta pronta
        worker = key.data
        answer = self.receive_message(worker.sock)
        self.matrix_resolver.build_matrix_result(
            result_matrix, answer.result, answer.row_id, answer.column_id)
        worker.is_busy = False
        received_results += 1
    self.dispatch_tasks(pending_tasks)         # quem liberou já recebe o próximo par
```

O `select()` devolve apenas os sockets com dados disponíveis, o que permite atender os cinco
trabalhadores **em uma única thread, sem locks**; o estado de cada um se resume ao `is_busy`. Os
sockets seguem bloqueantes: como o `recv()` só é chamado após o `select()` confirmar que há bytes,
ele não bloqueia na prática.

### 2.3 Comunicação síncrona

Na versão síncrona (`coordinate_sync`), o coordenador despacha uma única tarefa por vez e bloqueia
imediatamente em `receive_message(worker.sock)`, aguardando a resposta daquele trabalhador antes de
pegar o próximo par da fila:

```python
while pending_tasks:
    task = pending_tasks.popleft()
    worker = self.worker_connections[worker_idx % num_workers]
    worker_idx += 1

    self.send_message(worker.sock, task)
    answer = self.receive_message(worker.sock)   # Bloqueia no recv() até a resposta chegar

    self.matrix_resolver.build_matrix_result(
        result_matrix, answer.result, answer.row_id, answer.column_id
    )
```

Nesse modelo (*stop-and-wait* sequencial), o paralelismo dos nós é completamente anulado: enquanto
um trabalhador calcula e devolve o resultado, os demais permanecem ociosos aguardando a sua vez no
rodízio.

**Comparativo medido em localhost (matrizes 10 × 10, 100 tarefas, 5 trabalhadores):**
* **Modo Síncrono:** 0,0192 s (19,2 ms)
* **Modo Assíncrono:** 0,0040 s (4,0 ms)
* **Speedup Assíncrono:** **4,81× mais rápido**

Com 5 trabalhadores, o ganho de velocidade no modo assíncrono aproximou-se do limite teórico
($\approx 5\times$), comprovando a eficácia da multiplexação com `selectors` em manter todos os nós
ocupados simultaneamente sem contenção de threads.

---

## 3. Parte 2 — Middleware (gRPC)

Cada trabalhador publica o método remoto `DotProduct`; o coordenador o invoca como se fosse uma
função local. O serviço é registrado em tempo de execução pela API genérica do gRPC, sem arquivo
`.proto` e sem código gerado. O corpo da mensagem é o **mesmo JSON da Parte 1**, então a
serialização se resume a `encode`/`decode`:

```python
handler = grpc.method_handlers_generic_handler("matrixmultiplication.MatrixWorker", {
    "DotProduct": grpc.unary_unary_rpc_method_handler(
        self.dot_product,
        request_deserializer=lambda body: body.decode(),
        response_serializer=lambda body: body.encode())})
server.add_generic_rpc_handlers((handler,))
```

O método remoto no trabalhador não tem uma linha de rede:

```python
def dot_product(self, request: str, context) -> str:
    payload = Payload.from_json(request)
    payload.result = self.matrix_resolver.multiply_column_by_row(payload)
    return payload.to_json()
```

No coordenador, o equivalente ao *stub* sai do canal (`channel.unary_unary(...)`). A chamada
assíncrona usa `.future()`, que retorna imediatamente, e um *callback* que deposita a resposta numa
fila:

```python
call = worker.dot_product.future(task.to_json())
call.add_done_callback(lambda finished_call, w=worker: completed_calls.put((w, finished_call)))
```

O laço principal tem o mesmo formato da Parte 1 — só o ponto de espera muda:

| Parte 1 | Parte 2 |
|---|---|
| `self.selector.select()` | `completed_calls.get()` |
| "quais sockets têm bytes prontos" | "qual chamada remota terminou" |

---

## 4. Exemplos de execução

Matrizes 3 × 3, cinco trabalhadores ativos nas duas partes:

```
A = [2, 1, 5]    B = [7, 1, 1]
    [4, 4, 3]        [2, 4, 4]
    [2, 9, 2]        [9, 1, 9]
```

**Parte 1 — sockets** (saída reduzida) e a saída simultânea de um dos trabalhadores:

```
[COORD] 9 pares (linha, coluna) a distribuir     [WORKER 30010] Coordenador conectado
[COORD] 5 worker(s) disponível(is)               [WORKER 30010] linha 0 x coluna 0 = 61
[COORD] worker 1 devolveu resultado[0][1] = 11   [WORKER 30010] linha 2 x coluna 0 = 50
[COORD] worker 4 devolveu resultado[1][1] = 23
[COORD] worker 2 devolveu resultado[0][2] = 51     [COORD] Matriz resultado:
[COORD] worker 0 devolveu resultado[0][0] = 61        [61, 11, 51]
   (... demais pares ...)                             [63, 23, 47]
                                                      [50, 40, 56]
```

**Parte 2 — gRPC** (saída reduzida):

```
[GRPC COORD] 9 chamadas remotas a distribuir       [GRPC COORD] Matriz resultado:
[GRPC COORD] 5 worker(s) disponível(is)                  61    11    51
[GRPC COORD] worker 0 devolveu resultado[0][0] = 61      63    23    47
[GRPC COORD] worker 1 devolveu resultado[0][1] = 11      50    40    56
[GRPC COORD] worker 2 devolveu resultado[0][2] = 51
   (... demais chamadas ...)
```

Duas observações: **(a)** as respostas chegam fora de ordem nas duas partes (`[0][1]` antes de
`[0][0]` na Parte 1) e ainda assim a matriz é remontada corretamente, o que comprova que a
reconstrução depende dos índices e não da sequência; **(b)** as duas implementações produzem a
mesma matriz. Conferindo `[0][0]` manualmente: `2·7 + 1·2 + 5·9 = 61`. Para 10 × 10, as 100 células
foram comparadas com a multiplicação calculada diretamente em Python, com correspondência total.

---

## 5. Comparação crítica

### 5.1 Esforço de implementação

| | Parte 1 (socket TCP) | Parte 2 (gRPC) |
|---|---|---|
| Linhas de código de rede escritas à mão | 65 (38 coordenador + 27 worker) | 0 |
| Enquadramento das mensagens | manual (cabeçalho + leitura exata) | do middleware |
| Espera por múltiplas respostas | `selectors` + estado por worker | `future` + *callback* |
| Dependências externas | nenhuma (biblioteca padrão) | `grpcio` |
| Erros típicos no desenvolvimento | mensagem partida, leitura invadindo a próxima, *busy loop* de escrita | contrato divergente entre os lados |

O esforço da Parte 1 concentra-se em problemas **sem relação com multiplicar matrizes**: descobrir
onde uma mensagem termina, impedir que um `recv()` consuma bytes da próxima, evitar que o
`EVENT_WRITE` gire o laço em 100 % de CPU. Na Parte 2 esses problemas não existem. Em compensação,
a Parte 1 é transparente — todo byte trafegado está visível no código; no gRPC, um erro interno é
mais difícil de diagnosticar e o contrato (nome do serviço e do método) vira um acordo implícito
entre os dois lados, exatamente o que um arquivo `.proto` traria de volta ao custo de uma etapa de
geração de código.

### 5.2 Desempenho

Medições em `localhost`, matrizes 10 × 10 (100 tarefas), cinco trabalhadores:

| Métrica | Parte 1 (socket TCP) | Parte 2 (gRPC) |
|---|---|---|
| Estabelecer conexão com um worker | 0,11 ms | 1,73 ms |
| Uma chamada completa (ida e volta) | 0,038 ms | 0,297 ms |
| Chamadas por segundo (um worker) | ≈ 26.300 | ≈ 3.400 |
| Execução completa 10 × 10 | 0,003 s | 0,213 s |

O middleware custa cerca de **8× por chamada** e 16× para abrir a conexão — preço do HTTP/2, dos
metadados e das camadas de serialização. A última linha exige uma ressalva: dos 213 ms, apenas
14 ms são de conexão e 36 ms das 100 chamadas; **os 166 ms restantes são o fechamento dos cinco
canais**, contabilizado dentro do trecho cronometrado. A execução 1 × 1 (uma única chamada) também
leva 0,21 s, confirmando que esse custo é fixo e não proporcional ao trabalho.

Outra limitação do experimento: o produto escalar de vetores de 10 elementos leva microssegundos,
ou seja, **o custo de comunicação domina o de cálculo**. Nessa escala, distribuir sai mais caro que
calcular localmente; o ganho só aparece quando cada tarefa é computacionalmente pesada.

### 5.3 Quando usar cada abordagem

**Socket direto** compensa com protocolo simples e estável, desempenho por mensagem crítico e sem
dependências externas — ao custo de escrever e manter enquadramento, serialização e concorrência.
**Middleware** compensa quando a interface tende a crescer, há mais de uma linguagem envolvida ou
se quer recursos prontos (*deadline*, autenticação, *streaming*) — ao custo de latência maior, uma
dependência a mais e menos visibilidade do tráfego.

Para este trabalho, a diferença mais marcante não foi desempenho, e sim o **deslocamento do
esforço**: na Parte 1, a maior parte do tempo foi gasta com transporte; na Parte 2, com o problema.

---

## 6. Como executar

```bash
# Parte 1 — sem dependências
python3 WorkerServer.py 127.0.0.1 30010     # um terminal por worker (30010..30050)
python3 CordServer.py

# Parte 2 — requer grpcio
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 GrpcWorkerServer.py 127.0.0.1 50051 # um terminal por worker (50051..50055)
python3 GrpcCordServer.py 10                # argumento = tamanho da matriz
```

Não é obrigatório subir os cinco trabalhadores: o coordenador usa os que encontrar, desde que haja
ao menos um.
