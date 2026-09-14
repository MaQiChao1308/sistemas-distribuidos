# Created on Wed Sep  9 14:45:37 2026
# @author: massa
import Pyro5.api
import threading

# ==========================================
# 1. OBJETO DISTRIBUÍDO DO JOGADOR
# ==========================================
@Pyro5.api.expose
class Jogador:
    def __init__(self, nome):
        # Inicializa o jogador local expondo-o para RPC.
        # nome: Nome do jogador informado no terminal.
        
        # SISTEMA DE SINCRONIZAÇÃO DE MULTIPLOS EVENTOS (Semáforos binários):
        # Sinaliza para a Main Thread (CLI) que é o momento de ler o teclado.
        self.turno_evento = threading.Event()  
        
        # Sinaliza para a Thread de Rede (Pyro) que a jogada do teclado foi concluída.
        self.jogada_evento = threading.Event() 
        
        # Sinaliza para a Thread de Rede (Pyro) que a resposta de revanche foi concluída.
        self.revanche_evento = threading.Event()
        
        # Estado e controle do jogador
        self.jogada = None
        self.modo_input = "jogada" # Pode ser "jogada" ou "revanche"
        self.resposta_revanche = False
        self.jogo_ativo = True
        self.nome = nome

    # O decorador @oneway avisa ao middleware que o servidor não precisa 
    # aguardar um "return". É o equivalente a mensagens UDP (fire-and-forget).
    @Pyro5.api.oneway
    def receber_mensagem(self, msg):
        print(msg)

    def ping(self):
        # Método para verificação de conectividade pelo servidor
        return True

    @Pyro5.api.oneway
    def finalizar(self):
        self.jogo_ativo = False
        # Libera todos os semáforos para acordar a Main Thread e permitir encerramento limpo
        self.turno_evento.set() 
        self.jogada_evento.set()
        self.revanche_evento.set()

    def fazer_jogada(self):
        # Executado na thread do Pyro quando o servidor solicita um lance via RPC
        self.modo_input = "jogada"
        self.jogada_evento.clear()
        
        # Acorda a Main Thread para ler o lance no teclado
        self.turno_evento.set()
        
        # Aguarda a Main Thread concluir a digitação
        self.jogada_evento.wait()
        
        return self.jogada

    def perguntar_revanche(self):
        # Executado na thread do Pyro quando o servidor consulta sobre revanche via RPC
        self.modo_input = "revanche"
        self.revanche_evento.clear()
        
        # Acorda a Main Thread para ler a resposta de revanche
        self.turno_evento.set()
        
        # Aguarda a resposta ser informada no terminal
        self.revanche_evento.wait()
        
        return self.resposta_revanche

# ==========================================
# 2. INTERFACE E LOOP PRINCIPAL (MAIN THREAD)
# ==========================================
def main():
    nome = input("Digite seu nome: ").strip()
    while not nome:
        nome = input("Nome não pode ser vazio, digite novamente: ").strip()
    try:
        # Busca no Name Server o endereço de memória remoto do Servidor Principal
        ns = Pyro5.api.locate_ns()
        uri = ns.lookup("jogodavelha.servidor")
        servidor = Pyro5.api.Proxy(uri)
    except Exception as e:
        print("Erro ao localizar o servidor. O Name Server está rodando?", e)
        return

    # Registra este cliente na rede Pyro para que o Servidor possa invocar seus métodos
    jogador = Jogador(nome)
    daemon = Pyro5.api.Daemon()
    jogador_uri = daemon.register(jogador)

    # Inicia a escuta de chamadas do servidor em uma thread em background (Daemon).
    threading.Thread(target=daemon.requestLoop, daemon=True).start()

    print("Conectando ao servidor... Aguardando um adversário entrar na fila.")
    try:
        # Chama o método remoto do servidor, passando o endereço do cliente e o nome
        servidor.iniciar_jogo(str(jogador_uri), nome)
    except Exception as e:
        print(f"Erro ao registrar no servidor: {e}")
        return

    try:
        # Loop do CLI (Command Line Interface). 
        # Esta é a única thread que interage diretamente com sys.stdin (teclado).
        while jogador.jogo_ativo:
            
            # A thread entra em estado "SUSPENDED" (não gasta processamento) 
            # até que a thread do Pyro mude o estado do Evento para set().
            jogador.turno_evento.wait() 
            jogador.turno_evento.clear() # Reseta o evento para o próximo ciclo
            
            if not jogador.jogo_ativo:
                print("\nEncerrando o cliente...")
                break # Sai do while e finaliza o processo graciosamente
            
            if jogador.modo_input == "revanche":
                # Tratamento de resposta de revanche pelo teclado
                while True:
                    resp = input("\nDeseja jogar novamente? (s/n): ").strip().lower()
                    if resp in ["s", "sim"]:
                        jogador.resposta_revanche = True
                        break
                    elif resp in ["n", "nao", "não"]:
                        jogador.resposta_revanche = False
                        break
                    else:
                        print("Opção inválida. Digite 's' para sim ou 'n' para não.")
                
                # Destrava a thread do Pyro para devolver a resposta ao servidor
                jogador.revanche_evento.set()

            else:
                # Tratamento de lance comum da partida
                print(">>> É a sua vez!")
                
                # Loop de validação de entrada
                while True:
                    try:
                        linha = int(input("Linha (0-2): "))
                        coluna = int(input("Coluna (0-2): "))
                        
                        # Validação dupla (cliente e servidor) evita envios desnecessários pela rede
                        if 0 <= linha <= 2 and 0 <= coluna <= 2:
                            jogador.jogada = (linha, coluna)
                            break
                        else:
                            print("Por favor, digite valores válidos entre 0 e 2.")
                    except ValueError:
                        print("Entrada inválida. Digite apenas números inteiros.")
                
                # Avisa à thread do Pyro que os dados estão prontos.
                jogador.jogada_evento.set() 
            
    except KeyboardInterrupt:
        # Captura CTRL+C garantindo que o programa feche sem estourar Tracebacks feios.
        print("\nDesconectado pelo jogador (CTRL+C).")
    finally:
        # Garante a liberação de recursos do daemon local
        jogador.finalizar()
        try:
            daemon.shutdown()
        except:
            pass

if __name__ == "__main__":
    main()