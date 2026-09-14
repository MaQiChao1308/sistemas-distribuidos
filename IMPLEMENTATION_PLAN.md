# Plano de Implementação - Parte B: Evolução do Sistema (Jogo da Velha Distribuído)

Este plano contempla a evolução do sistema de Jogo da Velha distribuído usando **Pyro5**, cobrindo os três requisitos da **Parte B (70% da nota)**:
1. **Controle de Nomes de Usuários (20%)**
2. **Sistema de Pontuação Contínua / Revanche (30%)**
3. **Tolerância a Falhas / Desconexão com W.O. (20%)**

---

## 1. Análise dos Requisitos

### 1.1 Controle de Nomes de Usuários
- O cliente solicita o nome do jogador antes de se conectar ao servidor (já estruturado na etapa anterior).
- Lances, avisos de turno e anúncios de vitória devem exibir os nomes reais dos jogadores, substituindo mensagens genéricas ("Aguarde o turno de João", "João jogou na posição [1, 2]", "João venceu!").

### 1.2 Sistema de Pontuação Contínua (Revanche)
- Ao término de cada partida (vitória ou empate), a thread da partida **não** deve encerrar os clientes de imediato.
- O servidor exibirá o placar acumulado (ex: `João 2 x 1 Maria (Empates: 0)`).
- O servidor perguntará a ambos os jogadores via RPC se desejam jogar novamente (revanche).
- O cliente deve coordenar a leitura da resposta no terminal (`sys.stdin`) através de sincronização de eventos com a thread Pyro, sem concorrência ou bloqueio impróprio.
- Se ambos aceitarem, o tabuleiro é reiniciado e uma nova rodada começa na mesma thread (com alternância de quem inicia para garantir equilíbrio).
- Se qualquer um recusar (ou ambos), envia-se uma mensagem de encerramento amigável e ambos os clientes são finalizados.

### 1.3 Tolerância a Falhas / Desconexão (W.O.)
- Se um jogador fechar o terminal (CTRL+C) ou perder a conexão de rede a qualquer momento (durante o turno, espera ou revanche):
  - O middleware Pyro detectará a desconexão (exceções de comunicação ou timeout configurado `COMMTIMEOUT`).
  - O servidor identifica com precisão qual jogador desconectou e qual permaneceu conectado.
  - O jogador ativo recebe a mensagem: `"Oponente desconectado. Você venceu por W.O."` (com o nome do oponente).
  - O cliente ativo é finalizado graciosamente (`finalizar()`).
  - O servidor libera os proxies Pyro (`_pyroRelease()`) e encerra a thread sem deixar referências soltas na memória (evitando threads zumbis).
  - Adicionalmente: validação dos clientes na fila antes de iniciar a partida (verificação prévia de conectividade/ping).

---

## 2. Proposta de Alterações

### [JVClient.py](JVClient.py)
1. **Classe `Jogador`**:
   - Adicionar método exposto `perguntar_revanche(self)`:
     - Define `self.modo_input = "revanche"`.
     - Ativa `self.turno_evento.set()` para acordar a thread principal (CLI).
     - Aguarda em `self.revanche_evento.wait()` até que o jogador digite `s` ou `n`.
     - Retorna o booleano da resposta para o servidor via RPC.
   - Adicionar método `ping(self)` retornando `True` para teste de liveness pelo servidor.
   - Em `finalizar(self)`, liberar tanto `turno_evento` quanto `jogada_evento` e `revanche_evento` para destravar qualquer thread suspensa.
2. **Loop da Main Thread (`main`)**:
   - Tratar `self.modo_input == "revanche"` solicitando `"Deseja jogar novamente? (s/n): "`.
   - Tratar encerramento limpo no bloco `finally` para desligar o daemon Pyro (`daemon.shutdown()`).

---

### [JVServer.py](JVServer.py)
1. **Configuração do Pyro5**:
   - Ajustar `Pyro5.config.COMMTIMEOUT` (ex: 60s para lances ou timeouts adequados) garantindo que chamadas de rede não fiquem presas infinitamente se um socket morrer silenciosamente.
2. **Classe `ServidorJogo`**:
   - **`_partida(self, p1, p2)`**:
     - Manter dicionário de placar: `placar = {nome1: 0, nome2: 0, "empates": 0}`.
     - Loop de partidas contínuas (`while True` de revanche).
     - Informar o lance do jogador para o oponente (`f"{nome_jogador} jogou na linha {linha}, coluna {coluna}"`).
     - Em caso de vitória ou empate:
       - Atualizar o placar e exibi-lo formatado a ambos.
       - Invocar `perguntar_revanche()` para `j1` e `j2`.
       - Se ambos aceitarem, reiniciar o `Tabuleiro()`, alternar o jogador inicial e continuar o loop.
       - Se alguém recusar, notificar e chamar `finalizar()` em ambos.
     - **Tratamento de Exceções & W.O.**:
       - Capturar exceções de comunicação específicas do Pyro (`Pyro5.errors.CommunicationError`, `Pyro5.errors.ConnectionClosedError`, `Pyro5.errors.TimeoutError`, etc.).
       - Isolar qual jogador gerou a falha: se `j1` falhou, notificar `j2` com vitória por W.O. e vice-versa.
       - Executar `_pyroRelease()` nos proxies para liberar sockets e evitar vazamento de memória.
   - **Validação de fila em `iniciar_jogo`**:
     - Testar conectividade básica antes de iniciar thread de partida, garantindo que clientes que caíram na fila não iniciem partidas fantasmas.

---

### [README.md](README.md)
- Atualizar a documentação do projeto detalhando o funcionamento do sistema de revanche, tolerância a falhas (W.O.) e protocolo de encerramento.

---

## 3. Plano de Verificação

### Testes Automatizados
1. **Verificação de Sintaxe e Compilação**:
   - Executar `python3 -m py_compile JVClient.py JVServer.py`.
2. **Script de Teste de Integração Headless**:
   - Criar um script simulando dois clientes Pyro jogando:
     - Teste 1: Jogo completo com vitória de um jogador + aceite de revanche + 2ª partida + recusa de revanche -> encerramento correto com placar contínuo.
     - Teste 2: Desconexão abrupta (simulação de CTRL+C / fechamento de socket) -> oponente ativo recebe vitória por W.O. e servidor limpa recursos.

### Verificação Manual / Final
- Garantir que todos os comentários usem `#` conforme convenção solicitada.
- Realizar `git add`, `git commit` com mensagem descritiva e `git push origin main`.
