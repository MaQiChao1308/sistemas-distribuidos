# Sistema Distribuído de Relógios Vetoriais com Pyro5

Este projeto implementa um sistema distribuído em Python utilizando a biblioteca **Pyro5** (Python Remote Objects) para comunicação entre processos. O sistema simula processos concorrentes que geram e compartilham eventos, utilizando **Relógios Vetoriais** para rastrear a ordem causal e identificar eventos concorrentes.

---

## 📌 Requisitos Atendidos

1. **Processos Concorrentes**: 4 processos independentes ($P_1, P_2, P_3, P_4$) executados concorrentemente.
2. **Geração Aleatória de Eventos**: Cada processo gera eventos em intervalos aleatórios.
3. **Disseminação com Atraso Simultâneo**: Cada evento é enviado aos demais processos em threads separadas com atrasos aleatórios (`time.sleep`), fazendo com que mensagens cheguem em ordens distintas para cada destinatário.
4. **Regras de Relógios Vetoriais**:
   - **Evento Local / Envio**: $V_i[i] = V_i[i] + 1$
   - **Recepção de Mensagem**: $V_i[k] = \max(V_i[k], V_{msg}[k])$ para todos os $k$, seguido de $V_i[i] = V_i[i] + 1$.
5. **Logs e Visualização**:
   - Logs no terminal coloridos e formatados em tempo real.
   - Logs individuais salvos em `logs/process_P*.log`.
   - Log unificado estruturado em `logs/events_log.json`.
6. **Análise Causal e Concorrência**: Relatório pós-execução que compara todos os pares de eventos e destaca eventos concorrentes ($E_a \parallel E_b$).

---

## 🛠️ Estrutura do Projeto

```text
RelogiosVetoriais/
├── src/
│   ├── __init__.py
│   ├── vector_clock.py      # Implementação thread-safe das regras do Relógio Vetorial
│   ├── logger.py            # Logger com formatação ANSI e gravação em arquivos/JSON
│   ├── process_node.py      # Nó do processo (Pyro5 Daemon, RPC receiver e gerador de eventos)
│   └── causal_analyzer.py   # Analisador causal e detecção de concorrência pós-simulação
├── main.py                  # Orquestrador principal CLI (inicia NameServer, nós e simulação)
├── analyze_logs.py          # Script utilitário para analisar logs existentes
├── requirements.txt         # Dependências do projeto (Pyro5, serpent)
└── README.md                # Instruções e documentação
```

---

## 🚀 Como Executar

### 1. Criar e Ativar o Ambiente Virtual (Venv)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Executar a Simulação Principal

Para rodar a simulação com a duração padrão de **30 segundos** e 4 processos ($P_1, P_2, P_3, P_4$):

```bash
python3 main.py --duration 30
```

#### Opções de Linha de Comando (`main.py`):
- `--duration`: Duração da simulação em segundos (Ex: `--duration 30`).
- `--num-processes`: Número de processos concorrentes (Default: `4`).
- `--min-delay` / `--max-delay`: Faixa de atraso simulado no envio de mensagens em segundos (Default: `0.3` a `1.5`).
- `--min-interval` / `--max-interval`: Faixa de intervalo entre eventos locais em segundos (Default: `1.2` a `2.5`).
- `--no-analyze`: Desativa a exibição do relatório de concorrência ao final.

### 3. Analisar Logs Existentes

Você pode reexecutar a análise causal a qualquer momento utilizando o arquivo de log JSON gerado:

```bash
python3 analyze_logs.py
```

---

## 🔬 Conceitos de Relógios Vetoriais Aplicados

Dada uma coleção de $N$ processos $\{P_1, P_2, \dots, P_N\}$, cada processo $P_i$ mantém um vetor $V_i$ de tamanho $N$, onde $V_i[j]$ representa o conhecimento do processo $P_i$ sobre o número de eventos ocorridos em $P_j$.

### Comparação Causal entre dois eventos $E_1$ (com $V_1$) e $E_2$ (com $V_2$):
- **$V_1 \le V_2$**: $\forall k, V_1[k] \le V_2[k]$
- **$E_1$ antecede $E_2$ ($E_1 \to E_2$)**: $V_1 \le V_2$ e $V_1 \neq V_2$.
- **$E_1$ e $E_2$ são Concorrentes ($E_1 \parallel E_2$)**: $\neg(V_1 \le V_2) \land \neg(V_2 \le V_1)$.
