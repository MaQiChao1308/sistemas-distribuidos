# Sistemas Distribuídos - Jogo da Velha (Pyro5)

Implementação de um Jogo da Velha distribuído em Python utilizando **Pyro5** (Python Remote Objects) para comunicação RPC (Remote Procedure Call).

## Arquitetura do Sistema

- **Servidor (`JVServer.py`)**:
  - Padrão **Singleton** para centralizar o estado do jogo e a fila de jogadores.
  - Sincronização via `threading.Lock` para garantir operações thread-safe na fila de emparelhamento.
  - Inicialização de partidas em **threads dedicadas** (`_partida`), isolando cada dupla de jogadores.
  - Suporte a nomes personalizados dos jogadores durante a partida.

- **Cliente (`JVClient.py`)**:
  - Exposição de objeto remoto via Pyro (`@Pyro5.api.expose`) para permitir callbacks do servidor.
  - Sistema de sincronização com **duplo evento (semáforos binários)**: coordena a thread de rede (Pyro) e a thread principal de interface (CLI) sem consumo ativo de CPU.
  - Validação de entrada de nome e coordenadas de jogada.

## Como Executar

### 1. Iniciar o Name Server do Pyro5
Em um terminal, execute:
```bash
pyro5-ns
```

### 2. Iniciar o Servidor
Em outro terminal:
```bash
python3 JVServer.py
```

### 3. Iniciar os Clientes
Abra dois terminais adicionais para dois jogadores:
```bash
python3 JVClient.py
```
Informe o nome de cada jogador no terminal e aguarde o emparelhamento na fila para iniciar a partida.
