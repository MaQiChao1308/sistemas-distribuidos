# Sistema Publish-Subscribe (Pub/Sub) Intermediado com Pyro5

Sistema de comunicação indireta utilizando **Python 3** e **Pyro5**, composto por um **Intermediário (Broker)**, **Publishers** e **Subscribers**.

## 📁 Estrutura de Arquivos

- `intermediario.py`: Código-fonte do Intermediário (Broker) responsável por tópicos, inscrições e roteamento.
- `publisher.py`: Aplicação cliente Publisher para envio de mensagens.
- `subscriber.py`: Aplicação cliente Subscriber com objeto remoto de callback.
- `relatorio_tecnico.md`: Relatório técnico detalhado com diagramas, métodos remotos e fundamentação teórica.

---

## 🚀 Como Executar

### Pré-requisitos
Certifique-se de que o Pyro5 está instalado no seu ambiente Python:
```bash
pip install Pyro5
```

### 1. Iniciar o Pyro Name Server
Em um terminal, execute o servidor de nomes:
```bash
pyro5-ns
```

### 2. Iniciar o Intermediário (Broker)
Em um segundo terminal, execute o broker:
```bash
python3 intermediario.py
```

### 3. Iniciar um ou mais Subscribers
Em outros terminais, execute os subscribers informando o ID e opcionalmente tópicos iniciais:

```bash
# Subscriber S1 inscrito no tópico 'noticias'
python3 subscriber.py S1 noticias

# Subscriber S2 inscrito nos tópicos 'noticias' e 'esportes'
python3 subscriber.py S2 noticias esportes
```

Também é possível executar em modo interativo:
```bash
python3 subscriber.py S1
```

### 4. Publicar Mensagens (Publisher)

Você pode publicar via linha de comando rápida:
```bash
python3 publisher.py P1 noticias "Nova aula disponível."
python3 publisher.py P2 esportes "Jogo decisivo hoje à noite."
```

Ou em modo interativo com menu:
```bash
python3 publisher.py P1
```

---

## 📊 Formato das Mensagens Recebidas no Subscriber

Ao receber um evento publicado, o subscriber exibirá no terminal:
```text
[Mensagem recebida] Tópico: noticias Publisher: P1 Mensagem: Nova aula disponível.
```
