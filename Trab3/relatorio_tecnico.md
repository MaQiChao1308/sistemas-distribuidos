# Relatório Técnico: Sistema de Comunicação Publish-Subscribe Intermediado com Pyro5

**Disciplina:** Sistemas Distribuídos  
**Tecnologias:** Python 3, Pyro5 (Python Remote Objects), Pyro Name Server  

---

## 1. Arquitetura do Sistema

O sistema foi desenvolvido seguindo o padrão de arquitetura **Publish-Subscribe (Pub/Sub) Intermediado**. A comunicação entre os produtores de informação (*Publishers*) e os consumidores (*Subscribers*) ocorre de maneira totalmente indireta por meio de um componente centralizador (*Intermediário / Broker*).

```
                      ┌───────────────────────────┐
                      │     Pyro Name Server      │
                      │        (pyro5-ns)         │
                      └─────────────┬─────────────┘
                                    │ Registro / Resolução de Nomes
                                    ▼
┌─────────────────┐  Publica Mensagem  ┌───────────────────┐ Callback Remoto ┌─────────────────┐
│    Publisher    ├───────────────────►│   Intermediário   ├────────────────►│   Subscriber    │
│      (P1)       │                    │  (Broker Pub/Sub) │                 │   (S1, S2...)   │
└─────────────────┘                    └───────────────────┘                 └─────────────────┘
```

### Fluxo de Comunicação:
1. **Name Server**: O *Intermediário* registra seu nome lógico `intermediario.pubsub` no Pyro Name Server.
2. **Registro de Subscriber**: Cada *Subscriber* inicia seu próprio Pyro Daemon, registra uma URI de callback no *Intermediário* e inscreve-se nos tópicos de interesse.
3. **Publicação**: O *Publisher* conecta-se ao *Intermediário* via Name Server e invoca o método remoto `publicar(id_publisher, topico, mensagem)`.
4. **Encaminhamento**: O *Intermediário* consulta a tabela de inscrições e dispara chamadas remotas de callback (`notificar`) para todos os *Subscribers* inscritos naquele tópico.

---

## 2. Descrição dos Processos

### 2.1. Pyro Name Server (`pyro5-ns`)
Atua como o serviço de nomes centralizado. Permite que os processos localizem o Intermediário pelo seu nome simbólico (`intermediario.pubsub`), eliminando a necessidade de *hardcoding* de endereços IP ou portas.

### 2.2. Intermediário / Broker (`intermediario.py`)
Processo remoto principal. Mantém em memória:
- **Tópicos**: Conjunto de tópicos criados no sistema.
- **Subscribers**: Mapeamento dos identificadores dos subscribers (`id_subscriber`) para suas respectivas URIs de callback remoto (`uri_callback`).
- **Inscrições**: Mapeamento que associa cada tópico ao conjunto de subscribers inscritos.

### 2.3. Publisher (`publisher.py`)
Processo responsável por produzir mensagens. Conecta-se ao *Intermediário* via Pyro5 Proxy e disponibiliza uma interface CLI interativa (ou via linha de comando) para a publicação de mensagens em tópicos. **O Publisher não conhece a identidade, a quantidade ou a localização dos Subscribers.**

### 2.4. Subscriber (`subscriber.py`)
Processo consumidor. Executa um Pyro Daemon interno que expõe um objeto remoto da classe `SubscriberCallback`. Ao ser iniciado, o *Subscriber*:
1. Registra seu ID e a URI do seu callback no *Intermediário*.
2. Solicita a inscrição em um ou mais tópicos.
3. Aguarda e processa requisições de callback remoto enviadas pelo *Intermediário* quando novas mensagens são publicadas.

---

## 3. Métodos Remotos

### Métodos expostos pelo Intermediário (`intermediario.py`)

| Método | Parâmetros | Descrição |
| :--- | :--- | :--- |
| `criar_topico` | `nome: str` | Cria um novo tópico no sistema caso ainda não exista. |
| `registrar_subscriber` | `id_subscriber: str, uri_callback: str` | Registra o subscriber no broker associando seu ID à sua URI remota de callback. |
| `inscrever` | `id_subscriber: str, topico: str` | Adiciona o subscriber à lista de interessados no tópico (cria o tópico caso não exista). |
| `desinscrever` | `id_subscriber: str, topico: str` | Remove a inscrição do subscriber em um tópico específico. |
| `publicar` | `id_publisher: str, topico: str, mensagem: str` | Recebe a mensagem enviada por um publisher e a encaminha a todos os subscribers inscritos. |

### Método exposto pelo Subscriber (`subscriber.py`)

| Método | Parâmetros | Descrição |
| :--- | :--- | :--- |
| `notificar` | `topico: str, id_publisher: str, mensagem: str` | Invocado remotamente pelo *Intermediário* para entregar mensagens em tempo real ao subscriber. |

---

## 4. Encaminhamento de Mensagens (Mecanismo de Callback)

O encaminhamento de mensagens funciona através da técnica de **RMI Reversa / Callback Remoto**:

1. Quando o método `publicar(id_publisher, topico, mensagem)` é chamado no *Intermediário*, este verifica a lista de subscribers em `self.inscricoes[topico]`.
2. Para cada `id_subscriber` inscrito, recupera-se a `uri_callback` associada.
3. O *Intermediário* cria dinamicamente um *Proxy* para o objeto callback do *Subscriber*:
   ```python
   with Pyro5.api.Proxy(callback_uri) as sub_proxy:
       sub_proxy.notificar(topico, id_publisher, mensagem)
   ```
4. Se o *Subscriber* estiver offline ou inalcançável (gerando `CommunicationError`), o *Intermediário* remove automaticamente a inscrição do subscriber inativo para manter a consistência do sistema.

---

## 5. Utilização do Pyro5

O Pyro5 (Python Remote Objects) foi utilizado como middleware para gerenciamento da comunicação remota e invocação de métodos à distância (RMI):
- **`@Pyro5.api.expose`**: Decorator obrigatório para expor classes e métodos remotamente.
- **`Pyro5.api.Daemon`**: Gerencia o loop de escuta de conexões de entrada de cada processo servindo chamadas remotas (tanto no Intermediário quanto nos Subscribers).
- **`Pyro5.api.locate_ns()`**: Utilizado para conectar dinamicamente ao Pyro Name Server.
- **`Pyro5.api.Proxy`**: Cria um objeto cliente stubs local que traduz invocações de métodos em chamadas de rede.

---

## 6. Exemplos de Execução

### Passo 1: Iniciar o Name Server
```bash
pyro5-ns
```

### Passo 2: Iniciar o Intermediário
```bash
python3 intermediario.py
```
*Saída:*
```text
=================================================================
 INTERMEDIÁRIO (BROKER) PUBLISH-SUBSCRIBE PRONTO
 Registrado no Name Server como: 'intermediario.pubsub'
 Aguardando publicações e inscrições...
=================================================================
```

### Passo 3: Iniciar Subscribers (em terminais separados)
```bash
python3 subscriber.py S1 noticias
python3 subscriber.py S2 noticias esportes
```

### Passo 4: Publicar Mensagens (via Publisher)
```bash
python3 publisher.py P1 noticias "Nova aula disponível."
python3 publisher.py P2 esportes "Futebol hoje as 20h."
```

### Saída nos Subscribers:
**No terminal do Subscriber S1:**
```text
[Mensagem recebida] Tópico: noticias Publisher: P1 Mensagem: Nova aula disponível.
```

**No terminal do Subscriber S2:**
```text
[Mensagem recebida] Tópico: noticias Publisher: P1 Mensagem: Nova aula disponível.
[Mensagem recebida] Tópico: esportes Publisher: P2 Mensagem: Futebol hoje as 20h.
```

---

## 7. Comunicação Indireta e Desacoplamento

O modelo Publish-Subscribe implementado demonstra três dimensões fundamentais do desacoplamento em Sistemas Distribuídos:

1. **Desacoplamento Espacial (de Espaço)**:
   Publishers e Subscribers não precisam saber o endereço IP ou a porta um do outro. O Publisher interage unicamente com o Intermediário e especifica apenas o tópico de destino.
2. **Desacoplamento Temporal (de Tempo)**:
   Produtores e consumidores de mensagens não precisam coordenar o tempo de execução para iniciar a comunicação. Tópicos podem ser criados ou inscritos de forma assíncrona.
3. **Desacoplamento de Referência**:
   Os Publishers publicam eventos para o sistema sem manter qualquer lista de contatos ou estado dos receptores. O Intermediário assume a responsabilidade total pelo gerenciamento das inscrições e roteamento das mensagens.

                  ┌────────────────────┐
                  │  Pyro Name Server  │
                  └─────────┬──────────┘
         Busca NS           │(1) Registra nome     Busca NS
  ┌─────────────────────────┤    intermediario ◄─────────────── ┐
  │                         ▼                                   │
┌─┴───────┐ (3) publicar()┌──────────────────┐ (4) notificar()┌─┴───────┐
│Publisher├──────────────►│  Intermediário   ├───────────────►│Subscriber
│  (P1)   │               │ (Broker Pub/Sub) │                │(S1, S2) │
└─────────┘               └─────────┬────────┘                └────┬────┘
                                    │(2) registrar_subscriber(id)  │
                                    │    inscrever(id, topico)     │
                                    ◄──────────────────────────────┘