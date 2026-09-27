"""
publisher.py - Processo Publisher (Publicador) com Pyro5

Responsável por:
1. Conectar-se ao intermediário através do Pyro Name Server.
2. Criar tópicos (opcionalmente) e listar tópicos disponíveis.
3. Publicar mensagens informando seu id_publisher, o tópico e a mensagem.
4. Operar totalmente desacoplado dos subscribers (não conhece quem são nem quantos são).
"""

import sys
import Pyro5.api
import Pyro5.errors


def obter_intermediario():
    """
    Localiza o intermediário registrado no Pyro Name Server.
    """
    nome_servico = "intermediario.pubsub"
    try:
        intermediario = Pyro5.api.Proxy(f"PYRONAME:{nome_servico}")
        # Testa a conexão imediata com o objeto remoto
        intermediario._pyroBind()
        return intermediario
    except (Pyro5.errors.NamingError, Pyro5.errors.CommunicationError) as err:
        print("\n[ERRO] Não foi possível conectar ao Intermediário!")
        print(f"Motivo: {err}")
        print("Certifique-se de que:")
        print(" 1. O Name Server está rodando: pyro5-ns")
        print(" 2. O Intermediário está rodando: python3 intermidiate.py\n")
        return None


def modo_interativo(intermediario, id_publisher: str):
    """
    Menu interativo via terminal para publicar mensagens continuamente.
    """
    print("=" * 60)
    print(f" PUBLISHER INICIADO - Identificador: [{id_publisher}]")
    print(" Conectado com sucesso ao Intermediário.")
    print("=" * 60)

    while True:
        print("\nEscolha uma opção:")
        print(" 1. Publicar mensagem em um tópico")
        print(" 2. Criar novo tópico")
        print(" 3. Listar tópicos existentes no intermediário")
        print(" 0. Sair")

        opcao = input("\nOpção: ").strip()

        if opcao == "1":
            topico = input("Digite o nome do tópico: ").strip()
            if not topico:
                print("Nome do tópico não pode ser vazio.")
                continue

            mensagem = input("Digite a mensagem: ").strip()
            if not mensagem:
                print("Mensagem não pode ser vazia.")
                continue

            try:
                # Chama remotamente o método publicar do intermediário
                entregas = intermediario.publicar(id_publisher, topico, mensagem)
                print(f"[Sucesso] Mensagem enviada para o tópico '{topico}'. (Entregue a {entregas} subscriber(s))")
            except Exception as e:
                print(f"[Erro ao publicar] {e}")

        elif opcao == "2":
            topico = input("Digite o nome do novo tópico: ").strip()
            if not topico:
                print("Nome do tópico não pode ser vazio.")
                continue

            try:
                criado = intermediario.criar_topico(topico)
                if criado:
                    print(f"[Sucesso] Tópico '{topico}' criado no intermediário.")
                else:
                    print(f"[Aviso] Tópico '{topico}' já existe ou não pôde ser criado.")
            except Exception as e:
                print(f"[Erro ao criar tópico] {e}")

        elif opcao == "3":
            try:
                topicos = intermediario.listar_topicos()
                print(f"\nTópicos disponíveis ({len(topicos)}):")
                if topicos:
                    for t in topicos:
                        print(f" - {t}")
                else:
                    print(" (Nenhum tópico criado ainda)")
            except Exception as e:
                print(f"[Erro ao listar tópicos] {e}")

        elif opcao == "0":
            print(f"\nEncerrando Publisher [{id_publisher}]. Até logo!")
            break
        else:
            print("Opção inválida, tente novamente.")


def main():
    intermediario = obter_intermediario()
    if not intermediario:
        sys.exit(1)

    # Permite passar argumentos diretamente pela linha de comando:
    # Exemplo 1 (modo rápido): python3 publisher.py P1 noticias "Nova aula disponível."
    if len(sys.argv) >= 4:
        id_publisher = sys.argv[1].strip()
        topico = sys.argv[2].strip()
        mensagem = " ".join(sys.argv[3:]).strip()

        print(f"Publisher [{id_publisher}] publicando no tópico '{topico}': \"{mensagem}\"")
        try:
            entregas = intermediario.publicar(id_publisher, topico, mensagem)
            print(f"[OK] Mensagem entregue a {entregas} subscriber(s).")
        except Exception as e:
            print(f"[ERRO] Falha ao publicar: {e}")
        return

    # Exemplo 2 (modo interativo): python3 publisher.py P1
    if len(sys.argv) == 2:
        id_publisher = sys.argv[1].strip()
    else:
        # Pergunta no terminal
        id_publisher = input("Informe o identificador do Publisher (ex: P1): ").strip()
        if not id_publisher:
            id_publisher = "P1"

    modo_interativo(intermediario, id_publisher)


if __name__ == "__main__":
    main()
