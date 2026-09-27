"""
intermidiate.py - Intermediário (Broker) Publish-Subscribe com Pyro5

Responsável por:
1. Gerenciar tópicos (criar, listar).
2. Gerenciar registros de subscribers e suas inscrições nos tópicos.
3. Receber mensagens dos publishers e encaminhá-las aos subscribers interessados (via callback remoto).
"""

from collections import defaultdict
import Pyro5.api
import Pyro5.errors


@Pyro5.api.expose
class Intermediario:
    def __init__(self):
        # Conjunto de tópicos existentes
        self.topicos = set()
        
        # Mapeamento de subscribers registrados: { id_subscriber: uri_ou_proxy_callback }
        self.subscribers = {}
        
        # Mapeamento de inscrições: { topico: { id_subscriber_1, id_subscriber_2, ... } }
        self.inscricoes = defaultdict(set)
        
        print("[Intermediário] Inicializado com sucesso.")

    def criar_topico(self, nome: str) -> bool:
        """
        Cria um novo tópico se ele ainda não existir.
        """
        if not nome or not isinstance(nome, str):
            print("[Intermediário] Erro: Nome do tópico inválido.")
            return False
            
        nome = nome.strip()
        if nome in self.topicos:
            print(f"[Intermediário] Tópico '{nome}' já existe.")
            return False
        
        self.topicos.add(nome)
        print(f"[Intermediário] Tópico '{nome}' criado com sucesso.")
        return True

    def registrar_subscriber(self, id_subscriber: str, uri_callback: str = None) -> bool:
        """
        Registra um subscriber no intermediário.
        Aceita a URI do objeto de callback diretamente ou tenta localizá-la no Name Server.
        """
        if not id_subscriber:
            print("[Intermediário] Erro: id_subscriber não informado.")
            return False

        id_subscriber = str(id_subscriber).strip()

        if uri_callback:
            self.subscribers[id_subscriber] = uri_callback
            print(f"[Intermediário] Subscriber '{id_subscriber}' registrado com callback direto: {uri_callback}")
        else:
            # Caso não passe a URI diretamente, tenta localizar no Pyro Name Server
            try:
                ns = Pyro5.api.locate_ns()
                try:
                    uri = ns.lookup(f"subscriber.{id_subscriber}")
                except Exception:
                    uri = ns.lookup(id_subscriber)
                self.subscribers[id_subscriber] = uri
                print(f"[Intermediário] Subscriber '{id_subscriber}' localizado via Name Server: {uri}")
            except Exception:
                print(f"[Intermediário] Erro: Não foi possível obter o callback de '{id_subscriber}'.")
                return False
        return True

    def inscrever(self, id_subscriber: str, topico: str) -> bool:
        """
        Inscreve um subscriber previamente registrado em um tópico.
        """
        id_subscriber = str(id_subscriber).strip()
        topico = str(topico).strip()

        if id_subscriber not in self.subscribers:
            print(f"[Intermediário] Falha ao inscrever: Subscriber '{id_subscriber}' não está registrado.")
            return False

        # Se o tópico ainda não existe, cria automaticamente
        if topico not in self.topicos:
            print(f"[Intermediário] Tópico '{topico}' não existia. Criando automaticamente...")
            self.criar_topico(topico)

        self.inscricoes[topico].add(id_subscriber)
        print(f"[Intermediário] Subscriber '{id_subscriber}' inscrito no tópico '{topico}'.")
        return True

    def desinscrever(self, id_subscriber: str, topico: str) -> bool:
        """
        Remove a inscrição de um subscriber de um tópico específico.
        """
        id_subscriber = str(id_subscriber).strip()
        topico = str(topico).strip()

        if topico in self.inscricoes and id_subscriber in self.inscricoes[topico]:
            self.inscricoes[topico].remove(id_subscriber)
            print(f"[Intermediário] Subscriber '{id_subscriber}' desinscrito do tópico '{topico}'.")
            return True
        return False

    def publicar(self, id_publisher: str, topico: str, mensagem: str) -> int:
        """
        Recebe uma mensagem de um publisher e a encaminha aos subscribers inscritos no tópico.
        Retorna o total de subscribers notificados com sucesso.
        """
        id_publisher = str(id_publisher).strip()
        topico = str(topico).strip()

        print(f"\n[Publicação Recebida] Publisher: '{id_publisher}' | Tópico: '{topico}' | Mensagem: '{mensagem}'")

        if topico not in self.topicos:
            print(f"[Intermediário] Aviso: Tópico '{topico}' não existe. Mensagem descartada.")
            return 0

        subscribers_alvo = list(self.inscricoes.get(topico, []))
        if not subscribers_alvo:
            print(f"[Intermediário] Nenhum subscriber inscrito no tópico '{topico}'.")
            return 0

        sucessos = 0
        desconectados = []

        # Mecanismo de encaminhamento (Callback remoto para cada subscriber inscrito)
        for sub_id in subscribers_alvo:
            callback_uri = self.subscribers.get(sub_id)
            if not callback_uri:
                print(f"[Intermediário] Callback não configurado para subscriber '{sub_id}'.")
                continue

            try:
                with Pyro5.api.Proxy(callback_uri) as sub_proxy:
                    # Invoca método de callback no processo do subscriber
                    try:
                        sub_proxy.notificar(topico, id_publisher, mensagem)
                    except AttributeError:
                        sub_proxy.receber_mensagem(topico, id_publisher, mensagem)
                    
                    sucessos += 1
                    print(f" -> Encaminhado com sucesso para subscriber '{sub_id}'.")
            except (Pyro5.errors.CommunicationError, Pyro5.errors.PyroError) as err:
                print(f"[Intermediário] Erro de comunicação com subscriber '{sub_id}': {err}")
                print(f"[Intermediário] Marcando subscriber '{sub_id}' para remoção.")
                desconectados.append(sub_id)

        # Remove subscribers que caíram ou estão inacessíveis
        for sub_id in desconectados:
            self.remover_subscriber(sub_id)

        print(f"[Intermediário] Encaminhamento concluído: {sucessos}/{len(subscribers_alvo)} entregues.\n")
        return sucessos

    def remover_subscriber(self, id_subscriber: str):
        """
        Remove um subscriber das listas de registro e de todas as inscrições.
        """
        if id_subscriber in self.subscribers:
            del self.subscribers[id_subscriber]
        for topico in list(self.inscricoes.keys()):
            self.inscricoes[topico].discard(id_subscriber)
        print(f"[Intermediário] Subscriber '{id_subscriber}' removido completamente.")

    def listar_topicos(self) -> list:
        """Retorna a lista de tópicos existentes."""
        return sorted(list(self.topicos))

    def listar_subscribers(self) -> list:
        """Retorna a lista de subscribers registrados."""
        return sorted(list(self.subscribers.keys()))

    def listar_inscricoes(self) -> dict:
        """Retorna o dicionário de tópicos e seus respectivos subscribers."""
        return {topico: sorted(list(subs)) for topico, subs in self.inscricoes.items()}

    # Aliases em inglês para compatibilidade
    create_topic = criar_topico
    register_subscriber = registrar_subscriber
    subscribe = inscrever
    publish = publicar


def main():
    # 1. Criação do Daemon do Pyro5
    daemon = Pyro5.api.Daemon()

    # 2. Localização do Pyro Name Server
    try:
        ns = Pyro5.api.locate_ns()
    except Pyro5.errors.NamingError:
        print("\n[ERRO] Não foi possível localizar o Pyro Name Server!")
        print("Antes de iniciar o intermediário, execute em outro terminal:")
        print("    pyro5-ns\n")
        return

    # 3. Cria a instância do Intermediário e registra no Daemon
    intermediario = Intermediario()
    uri = daemon.register(intermediario)

    # 4. Registra no Name Server com o identificador padrão
    nome_servico = "intermediario.pubsub"
    ns.register(nome_servico, uri)

    print("=" * 65)
    print(" INTERMEDIÁRIO (BROKER) PUBLISH-SUBSCRIBE PRONTO")
    print(f" Registrado no Name Server como: '{nome_servico}'")
    print(f" URI: {uri}")
    print(" Aguardando publicações e inscrições...")
    print("=" * 65)

    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("\n[Intermediário] Encerrando intermediário...")
    finally:
        try:
            ns.remove(nome_servico)
        except Exception:
            pass
        daemon.close()
        print("[Intermediário] Finalizado com sucesso.")


if __name__ == "__main__":
    main()