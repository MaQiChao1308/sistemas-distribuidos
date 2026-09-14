# Sistemas Distribuídos - Jogo da Velha (Pyro5)

Implementação evoluída de um Jogo da Velha distribuído em Python utilizando **Pyro5** (Python Remote Objects) para comunicação RPC (Remote Procedure Call) bidirecional.

---

## Funcionalidades Implementadas (Parte B: Evolução do Sistema)

### 1. Controle de Nomes de Usuários (20%)
- **Entrada customizada**: O cliente solicita o nome do jogador antes de registrar sua presença no servidor.
- **Transparência e clareza**: Todas as mensagens da partida (anúncios de turno, lances efetuados, vitória e empate) utilizam os nomes reais dos jogadores, eliminando mensagens genéricas:
  - *"--- Nova rodada iniciada! Alice ('X') vs Bob ---"*
  - *"Aguarde o turno de 'Alice' ('X')..."*
  - *">> Alice jogou na linha 0, coluna 1."*
  - *"Fim de Jogo! O jogador 'Alice' (X) venceu!"*

### 2. Sistema de Pontuação Contínua e Revanche (30%)
- **Ciclo contínuo na mesma thread**: Ao término de cada partida, a conexão e a thread da partida permanecem ativas.
- **Placar acumulado**: O servidor exibe o placar em tempo real com vitórias de cada jogador e empates.
- **Protocolo de revanche bidirecional**:
  - O servidor consulta ambos os jogadores se desejam jogar novamente (`perguntar_revanche()`).
  - No cliente, semáforos de eventos (`revanche_evento`) sincronizam a thread Pyro com a leitura via `sys.stdin` na Main Thread.
  - Se **ambos aceitarem**, um novo tabuleiro é gerado e quem inicia a rodada é alternado para garantir justiça esportiva.
  - Se **um ou ambos recusarem**, o servidor envia uma mensagem amigável com o placar final e encerra ambos os clientes de forma elegante.

### 3. Tolerância a Falhas e Desconexão com W.O. (20%)
- **Detecção de desconexão e timeouts**:
  - Configuração global e por proxy de timeout (`Pyro5.config.COMMTIMEOUT = 45.0`) prevenindo bloqueios por conexões pendentes.
  - Verificação de conectividade na fila antes do pareamento com método `ping()` rápido.
  - Tratamento refinado de exceções de rede (`CommunicationError`, `ConnectionClosedError`, `TimeoutError`, etc.).
- **Vitória por W.O.**:
  - Se um jogador interromper o processo (`CTRL+C`) ou perder a conexão de rede durante o jogo ou a pergunta de revanche, o servidor identifica o oponente remanescente e envia:  
    `"Oponente '[Nome]' desconectado. Você venceu por W.O.!"`
- **Prevenção de vazamento de memória e threads zumbis**:
  - Liberação forçada dos proxies Pyro via `_pyroRelease()` no bloco `finally`.
  - Finalização controlada do daemon do cliente e limpeza do estado no servidor.

---

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
