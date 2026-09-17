# Walkthrough - Parte B: Evolução do Sistema (Jogo da Velha Distribuído)

Este documento sumariza as funcionalidades implementadas, os padrões de concorrência e rede adotados, e os testes de validação realizados para a **Parte B: Evolução do Sistema (70% da nota)**.

---

## 1. Funcionalidades Entregues

### A. Controle de Nomes de Usuários (20%)
- **Identificação Inicial**: O cliente [JVClient.py](JVClient.py) solicita o nome do jogador antes de registrar-se no Name Server e no Servidor.
- **Transparência de Lances e Turnos**: Substituição de mensagens genéricas por menções nominais:
  - Anúncio de rodada: `--- Nova rodada iniciada! {nome1} ('X') vs {nome2} ---`
  - Aviso de espera de turno: `Aguarde o turno de '{nome_jogador}' ('{simbolo}')...`
  - Feedback de lance efetuado para o oponente: `>> {nome_jogador} jogou na linha {linha}, coluna {coluna}.`
  - Anúncio de vitória: `Fim de Jogo! O jogador '{nome_vencedor}' ({vencedor}) venceu!`

### B. Sistema de Pontuação Contínua / Revanche (30%)
- **Manutenção de Conexão**: As threads das partidas no servidor não encerram os clientes após o fim de uma rodada.
- **Placar Acumulado**: O servidor contabiliza vitórias de cada jogador e empates em um dicionário `placar`, exibindo-o a cada fim de partida.
- **Coordenação no Cliente**: O método `perguntar_revanche()` sincroniza com a Main Thread via `self.revanche_evento`, liberando a leitura no terminal sem colisão com `fazer_jogada()`.
- **Alternância de Quem Começa**: Em partidas de revanche consecutivas, a ordem inicial de jogada alterna (`inicio_rodada = 1 - inicio_rodada`) para assegurar equilíbrio competitivo.
- **Encerramento Amigável**: Caso qualquer jogador recuse a revanche, ambos recebem uma notificação amigável com o placar final e o cliente encerra graciosamente.

### C. Tolerância a Falhas / Desconexão com W.O. (20%)
- **Timeouts de Rede**: Definido `Pyro5.config.COMMTIMEOUT = 45.0` e `_pyroTimeout` individual nos proxies, prevenindo travamento permanente da thread se um socket for interrompido.
- **Detecção de Quedas na Fila**: O servidor testa a conectividade dos candidatos na fila via `ping()` antes de formar uma partida, descartando clientes que fecharam antes do pareamento.
- **Tratamento de CTRL+C e Quedas de Conexão**:
  - Se um jogador desconecta durante o turno, envio de mensagens ou na consulta de revanche, o servidor identifica o oponente ativo e declara vitória por W.O.:
    `[AVISO] Oponente '{desconectado}' desconectou. Você venceu por W.O.!`
  - O cliente ativo é finalizado sem travar.
- **Prevenção de Threads Zumbis e Vazamento de Memória**:
  - No bloco `finally` de cada partida, os proxies Pyro executam `_pyroRelease()` explicitamente para fechar conexões e desalocar recursos da memória do servidor.

---

## 2. Validação e Testes Automatizados

Foi desenvolvido e executado um conjunto abrangente de testes de integração headless:

| Cenário de Teste | Descrição | Resultado |
|---|---|---|
| **Teste 1: Revanche e Placar** | Simulação de 2 partidas consecutivas na mesma thread, vitória alternada, atualização de placar e encerramento com recusa. | **PASSOU** |
| **Teste 2: Tolerância a Falhas (W.O.)** | Queda abrupta de conexão durante o turno de um jogador. Oponente ativo recebe W.O. e recursos são liberados. | **PASSOU** |
| **Teste 3: Desconexão na Revanche** | Queda de um cliente durante a pergunta de revanche. O oponente ativo recebe W.O. e é finalizado com segurança. | **PASSOU** |

---

## 3. Padrão de Comentários
- Todos os comentários e documentações do código fonte seguem estritamente o padrão com `#` conforme convenção solicitada pelo usuário.
