
import sys
import threading
import time
import Pyro5.api
import Pyro5.errors

"""
subscriber.py - Processo Subscriber (Inscrito/Assinante) com Pyro5

Responsável por:
1. Conectar-se ao Intermediário através do Pyro Name Server.
2. Expor um objeto remoto Callback para receber notificações do Intermediário.
3. Registrar-se no Intermediário informando seu ID e sua URI de callback.
4. Inscrever-se em um ou mais tópicos.
5. Receber e exibir em tempo real as mensagens enviadas pelos Publishers via Intermediário.
"""

@Pyro5.api.expose
class SubscriberCallback:
    """
    Objeto remoto exposto pelo Subscriber para receber mensagens encaminhadas pelo Intermediário.
    """
    def __init__(self, id_subscriber: str):
        self.id_subscriber = id_subscriber

    def notificar(self, topico: str, id_publisher: str, mensagem: str):
        """
        Método remoto invocado pelo Intermediário quando uma nova mensagem é publicada.
        Exibe a mensagem no formato especificado no trabalho.
        """
        print(f"\n[Mensagem recebida] Tópico: {topico} Publisher: {id_publisher} Mensagem: {mensagem}")
        print(f"[{self.id_subscriber}] Menu (ou aperte Enter) > ", end="", flush=True)

    def receber_mensagem(self, topico: str, id_publisher: str, mensagem: str):
        """Método alternativo de callback (alias)."""
        self.notificar(topico, id_publisher, mensagem)


def obter_intermediario():
    """
    Localiza o Intermediário no Pyro Name Server.
    """
    nome_servico = "intermediario.pubsub"
    try:
        intermediario = Pyro5.api.Proxy(f"PYRONAME:{nome_servico}")
        intermediario._pyroBind()
        return intermediario
    except (Pyro5.errors.NamingError, Pyro5.errors.CommunicationError) as err:
        print("\n[ERRO] Não foi possível conectar ao Intermediário!")
        print(f"Motivo: {err}")
        print("Certifique-se de que:")
        print(" 1. O Name Server está rodando: pyro5-ns")
        print(" 2. O Intermediário está rodando: python3 intermediario.py\n")
        return None


def modo_interativo(intermediario, id_subscriber: str, inscricoes_iniciais: list = None):
    """
    Inicia o daemon do Pyro em uma thread separada para escutar mensagens remotas
    enquanto permite a interação do usuário via terminal.
    """
    # 1. Configuração do Daemon do Subscriber
    daemon = Pyro5.api.Daemon()
    callback_obj = SubscriberCallback(id_subscriber)
    uri_callback = daemon.register(callback_obj)

    # Registra a URI de callback também no Name Server para contingência
    try:
        ns = Pyro5.api.locate_ns()
        ns.register(f"subscriber.{id_subscriber}", uri_callback)
    except Exception:
        pass

    # Inicia a thread do Daemon para escutar chamadas remotas do Intermediário
    daemon_thread = threading.Thread(target=daemon.requestLoop, daemon=True)
    daemon_thread.start()

    # 2. Registrar Subscriber no Intermediário
    try:
        registrado = intermediario.registrar_subscriber(id_subscriber, str(uri_callback))
        if not registrado:
            print(f"[ERRO] Não foi possível registrar o subscriber '{id_subscriber}' no Intermediário.")
            daemon.close()
            return
    except Exception as e:
        print(f"[ERRO] Falha na comunicação ao registrar subscriber: {e}")
        daemon.close()
        return

    print("=" * 65)
    print(f" SUBSCRIBER INICIADO - Identificador: [{id_subscriber}]")
    print(f" Callback URI: {uri_callback}")
    print(" Conectado e registrado com sucesso no Intermediário.")
    print("=" * 65)

    minhas_inscricoes = set()

    # 3. Inscrever nos tópicos passados por argumento (se houver)
    if inscricoes_iniciais:
        for t in inscricoes_iniciais:
            try:
                if intermediario.inscrever(id_subscriber, t):
                    minhas_inscricoes.add(t)
                    print(f"[Sucesso] Inscrito automaticamente no tópico '{t}'.")
            except Exception as e:
                print(f"[ERRO] Falha ao inscrever em '{t}': {e}")

    # 4. Loop de Menu Interativo
    try:
        while True:
            print(f"\n--- MENU SUBSCRIBER [{id_subscriber}] ---")
            print(" 1. Inscrever em um tópico")
            print(" 2. Desinscrever de um tópico")
            print(" 3. Listar tópicos disponíveis no Intermediário")
            print(" 4. Listar minhas inscrições ativas")
            print(" 5. Modo silencioso (Aguardar mensagens apenas)")
            print(" 0. Sair")

            opcao = input(f"[{id_subscriber}] Escolha uma opção: ").strip()

            if opcao == "1":
                topico = input("Digite o nome do tópico para inscrição: ").strip()
                if not topico:
                    print("Nome do tópico não pode ser vazio.")
                    continue
                try:
                    sucesso = intermediario.inscrever(id_subscriber, topico)
                    if sucesso:
                        minhas_inscricoes.add(topico)
                        print(f"[Sucesso] Você foi inscrito no tópico '{topico}'.")
                    else:
                        print(f"[Aviso] Não foi possível se inscrever no tópico '{topico}'.")
                except Exception as e:
                    print(f"[Erro ao inscrever] {e}")

            elif opcao == "2":
                if not minhas_inscricoes:
                    print("Você ainda não está inscrito em nenhum tópico.")
                    continue
                print(f"Suas inscrições: {', '.join(sorted(list(minhas_inscricoes)))}")
                topico = input("Digite o nome do tópico para cancelar inscrição: ").strip()
                try:
                    desinscrito = intermediario.desinscrever(id_subscriber, topico)
                    if desinscrito:
                        minhas_inscricoes.discard(topico)
                        print(f"[Sucesso] Inscrição removida do tópico '{topico}'.")
                    else:
                        print(f"[Aviso] Tópico '{topico}' não estava na sua lista de inscrições.")
                except Exception as e:
                    print(f"[Erro ao desinscrever] {e}")

            elif opcao == "3":
                try:
                    topicos = intermediario.listar_topicos()
                    print(f"\nTópicos no Intermediário ({len(topicos)}):")
                    if topicos:
                        for t in topicos:
                            status = "(Inscrito)" if t in minhas_inscricoes else ""
                            print(f" - {t} {status}")
                    else:
                        print(" (Nenhum tópico cadastrado no momento)")
                except Exception as e:
                    print(f"[Erro ao listar tópicos] {e}")

            elif opcao == "4":
                print(f"\nSuas inscrições ativas ({len(minhas_inscricoes)}):")
                if minhas_inscricoes:
                    for t in sorted(list(minhas_inscricoes)):
                        print(f" - {t}")
                else:
                    print(" (Você não está inscrito em nenhum tópico no momento)")

            elif opcao == "5":
                print("\n[Modo Escuta] Aguardando mensagens remotas em segundo plano... (Pressione Ctrl+C para voltar ao menu)")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nRetornando ao menu principal...")

            elif opcao == "0":
                print(f"\nEncerrando Subscriber [{id_subscriber}]...")
                break
            else:
                print("Opção inválida, tente novamente.")

    except KeyboardInterrupt:
        print(f"\n[Subscriber {id_subscriber}] Interrupção recebida. Encerrando...")
    finally:
        # Limpeza ao sair: desregistra e fecha daemon
        try:
            intermediario.remover_subscriber(id_subscriber)
        except Exception:
            pass
        try:
            ns = Pyro5.api.locate_ns()
            ns.remove(f"subscriber.{id_subscriber}")
        except Exception:
            pass
        daemon.close()
        print(f"[Subscriber {id_subscriber}] Encerrado com sucesso.")


def main():
    intermediario = obter_intermediario()
    if not intermediario:
        sys.exit(1)

    # Exemplo 1: python3 subscriber.py S1 noticias esportes
    if len(sys.argv) >= 2:
        id_subscriber = sys.argv[1].strip()
        topicos_iniciais = [t.strip() for t in sys.argv[2:] if t.strip()]
    else:
        id_subscriber = input("Informe o identificador do Subscriber (ex: S1): ").strip()
        if not id_subscriber:
            id_subscriber = "S1"
        topicos_iniciais = []

    modo_interativo(intermediario, id_subscriber, topicos_iniciais)


if __name__ == "__main__":
    main()
