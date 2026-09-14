# Created on Wed Sep  9 14:45:37 2026
# @author: massa
import Pyro5.api
import threading

# ==========================================
# 1. ABSTRAÇÃO: LÓGICA DE ESTADO DO JOGO
# ==========================================
# Esta classe encapsula as regras de negócio. Ao isolar o tabuleiro,
# garantimos que a lógica da rede não interfira nas regras do jogo (Alta Coesão).
class Tabuleiro:
    def __init__(self):
        # Matriz 3x3 representando o estado inicial do jogo vazio
        self.tabuleiro = [[" " for _ in range(3)] for _ in range(3)]

    def exibir(self):
        # Transforma a matriz em uma representação visual em string para o terminal
        return "\n".join([" | ".join(linha) for linha in self.tabuleiro])

    def jogar(self, linha, coluna, simbolo):
        # Validação de limites (segurança contra entradas maliciosas ou incorretas)
        if 0 <= linha <= 2 and 0 <= coluna <= 2:
            # Garante que a posição não foi sobrescrita
            if self.tabuleiro[linha][coluna] == " ":
                self.tabuleiro[linha][coluna] = simbolo
                return True
        return False

    def verificar_vencedor(self):
        # RECONHECIMENTO DE PADRÕES:
        # Agrupamos todas as combinações possíveis de vitória para analisá-las de forma uniforme.
        # Isso evita dezenas de "if/else" repetitivos.
        linhas = self.tabuleiro
        colunas = list(zip(*self.tabuleiro)) # Transposição da matriz (lê colunas como linhas)
        diagonais = [
            [self.tabuleiro[i][i] for i in range(3)],
            [self.tabuleiro[i][2 - i] for i in range(3)]
        ]

        # Itera sobre todas as trilhas possíveis buscando uma onde os 3 elementos são iguais e não vazios
        for trio in linhas + colunas + diagonais:
            if trio[0] != " " and trio.count(trio[0]) == 3:
                return trio[0] # Retorna "X" ou "O"
        return None

    def completo(self):
        # Verifica se ainda há espaços em branco. Útil para declarar empate (Deu Velha).
        return all(cell != " " for row in self.tabuleiro for cell in row)


# Configuração global de timeout do Pyro5 para evitar bloqueios indefinidos em sockets inativos
Pyro5.config.COMMTIMEOUT = 45.0

# ==========================================
# 2. DECOMPOSIÇÃO: GERENCIAMENTO DE REDE
# ==========================================
# O decorador @expose diz ao middleware do Pyro que os métodos públicos desta 
# classe estão liberados para serem acessados remotamente pelos clientes.
@Pyro5.api.expose
class ServidorJogo:
    def __init__(self):
        # O __init__ agora será executado UMA ÚNICA VEZ (Padrão Singleton implementado na main).
        self.fila = []
        # Mutex (Lock) necessário para evitar condições de corrida (Race Conditions)
        # caso dezenas de clientes tentem se conectar no exato mesmo milissegundo.
        self.lock = threading.Lock()
        print("[SISTEMA] Estrutura de dados do servidor iniciada.")

    def iniciar_jogo(self, jogador_uri, nome):
        # Recebe a conexão de um jogador, armazenando sua URI e Nome na fila.
        # Quando dois jogadores estão disponíveis, inicia uma thread de partida independente.
        # jogador_uri: Endereço do objeto remoto do cliente (Pyro URI).
        # nome: Nome de exibição do jogador.
        
        # ==========================================
        # CONCORRÊNCIA DO PYRO5 (Ownership):
        # Não instanciamos o Proxy() aqui na thread principal. 
        # O Pyro amarra o Proxy à thread que o criou. Se criarmos aqui, 
        # a thread da partida (que roda em background) não terá permissão para usá-lo.
        # Por isso, guardamos apenas a STRING (URI) na fila.
        # ==========================================
        print(f"[REDE] Novo jogador conectado: '{nome}' (URI: {jogador_uri})")
        
        # Seção Crítica: O Lock garante que apenas uma thread altere a fila por vez
        with self.lock:
            self.fila.append((jogador_uri, nome))
            
            # Algoritmo de emparelhamento com verificação de liveness
            if len(self.fila) >= 2:
                jogadores_ativos = []
                while self.fila and len(jogadores_ativos) < 2:
                    candidato = self.fila.pop(0)
                    try:
                        # Validação rápida de conectividade antes de criar a partida
                        teste = Pyro5.api.Proxy(candidato[0])
                        teste._pyroTimeout = 3.0
                        teste.ping()
                        teste._pyroRelease()
                        jogadores_ativos.append(candidato)
                    except Exception:
                        print(f"[AVISO] Jogador '{candidato[1]}' desconectou enquanto aguardava na fila.")

                if len(jogadores_ativos) == 2:
                    p1 = jogadores_ativos[0]
                    p2 = jogadores_ativos[1]
                    print(f"[SISTEMA] Partida formada: {p1[1]} vs {p2[1]}. Iniciando...")
                    
                    # A partida roda em uma nova Thread dedicada, recebendo os dados dos jogadores (p1, p2).
                    threading.Thread(target=self._partida, args=(p1, p2), daemon=True).start()
                elif len(jogadores_ativos) == 1:
                    # Devolve o jogador remanescente para o topo da fila
                    self.fila.insert(0, jogadores_ativos[0])


    # ==========================================
    # 3. MÁQUINA DE ESTADOS DA PARTIDA
    # ==========================================
    def _partida(self, p1, p2):
        # Controla a partida entre dois jogadores em uma thread dedicada.
        # p1: Tupla (uri1, nome1) do primeiro jogador.
        # p2: Tupla (uri2, nome2) do segundo jogador.
        uri1, nome1 = p1
        uri2, nome2 = p2
        
        # CONCORRÊNCIA DO PYRO5 (Ownership):
        # Os proxies são instanciados AQUI, dentro da thread que vai 
        # efetivamente usá-los para se comunicar com os clientes via RPC.
        j1 = Pyro5.api.Proxy(uri1)
        j2 = Pyro5.api.Proxy(uri2)
        j1._pyroTimeout = 45.0
        j2._pyroTimeout = 45.0

        # Sistema de pontuação contínua (Revanche)
        placar = {nome1: 0, nome2: 0, "empates": 0}
        inicio_rodada = 0 # Alterna quem começa a cada rodada

        # Função auxiliar para tratar desconexão e declarar vitória por W.O.
        def tratar_wo(desconectado_nome, oponente_proxy, oponente_nome):
            print(f"[TOLERÂNCIA A FALHAS] Desconexão de '{desconectado_nome}'. Declarando W.O. para '{oponente_nome}'.")
            try:
                oponente_proxy.receber_mensagem(f"\n[AVISO] Oponente '{desconectado_nome}' desconectou. Você venceu por W.O.!")
                oponente_proxy.finalizar()
            except Exception:
                pass

        try:
            # Loop de partidas contínuas (Revanche)
            while True:
                tab = Tabuleiro()
                jogadores = [(j1, "X", nome1), (j2, "O", nome2)]

                # Envia mensagem de boas-vindas da rodada
                try:
                    for jogador, simbolo, nome_proprio in jogadores:
                        outro_nome = nome2 if simbolo == "X" else nome1
                        jogador.receber_mensagem(f"\n--- Nova rodada iniciada! {nome_proprio} ('{simbolo}') vs {outro_nome} ---")
                except Exception as e:
                    # Falha logo na abertura da rodada
                    print(f"[ERRO] Falha ao iniciar rodada: {e}")
                    break

                atual = inicio_rodada # Índice do jogador atual (0 ou 1)

                # Loop de lances de uma partida
                while True:
                    jogador, simbolo, nome_jogador = jogadores[atual]
                    outro_jogador, outro_simbolo, outro_nome = jogadores[1 - atual]

                    # Envia estado do tabuleiro e notificação de turno com nome
                    try:
                        jogador.receber_mensagem("\n" + tab.exibir())
                        outro_jogador.receber_mensagem("\n" + tab.exibir())
                        outro_jogador.receber_mensagem(f"Aguarde o turno de '{nome_jogador}' ('{simbolo}')...")
                    except Exception:
                        # Se falhar ao enviar para o outro_jogador, ele desconectou
                        tratar_wo(outro_nome, jogador, nome_jogador)
                        return

                    # Ponto de sincronização: espera a jogada do cliente pela rede
                    try:
                        linha, coluna = jogador.fazer_jogada()
                    except Exception:
                        # Se o jogador do turno fechou o terminal ou caiu a conexão
                        tratar_wo(nome_jogador, outro_jogador, outro_nome)
                        return

                    # Processa o lance
                    if tab.jogar(linha, coluna, simbolo):
                        # Informa ao oponente exatamente qual lance foi executado
                        try:
                            outro_jogador.receber_mensagem(f">> {nome_jogador} jogou na linha {linha}, coluna {coluna}.")
                        except Exception:
                            tratar_wo(outro_nome, jogador, nome_jogador)
                            return

                        vencedor = tab.verificar_vencedor()

                        if vencedor:
                            nome_vencedor = nome1 if vencedor == "X" else nome2
                            placar[nome_vencedor] += 1
                            msg_vitoria = f"\n{tab.exibir()}\nFim de Jogo! O jogador '{nome_vencedor}' ({vencedor}) venceu!"
                            try:
                                j1.receber_mensagem(msg_vitoria)
                                j2.receber_mensagem(msg_vitoria)
                            except Exception:
                                pass
                            break
                        elif tab.completo():
                            placar["empates"] += 1
                            msg_empate = f"\n{tab.exibir()}\nFim de Jogo! Empate!"
                            try:
                                j1.receber_mensagem(msg_empate)
                                j2.receber_mensagem(msg_empate)
                            except Exception:
                                pass
                            break

                        # Alterna o turno
                        atual = 1 - atual
                    else:
                        try:
                            jogador.receber_mensagem("Jogada inválida! Posição ocupada ou fora dos limites.")
                        except Exception:
                            tratar_wo(nome_jogador, outro_jogador, outro_nome)
                            return

                # Exibe o placar contínuo atualizado a ambos os jogadores
                msg_placar = (
                    f"\n=============================\n"
                    f"        PLACAR ATUAL\n"
                    f"  {nome1}: {placar[nome1]} vitória(s)\n"
                    f"  {nome2}: {placar[nome2]} vitória(s)\n"
                    f"  Empates: {placar['empates']}\n"
                    f"============================="
                )
                try:
                    j1.receber_mensagem(msg_placar)
                    j2.receber_mensagem(msg_placar)
                except Exception:
                    pass

                # Consulta sobre a revanche
                try:
                    j1.receber_mensagem("\nAguardando confirmação de revanche...")
                    j2.receber_mensagem("\nAguardando confirmação de revanche...")
                except Exception:
                    pass

                # Solicita resposta do jogador 1
                try:
                    resp1 = j1.perguntar_revanche()
                except Exception:
                    tratar_wo(nome1, j2, nome2)
                    return

                # Solicita resposta do jogador 2
                try:
                    resp2 = j2.perguntar_revanche()
                except Exception:
                    tratar_wo(nome2, j1, nome1)
                    return

                # Avalia as respostas de revanche
                if resp1 and resp2:
                    try:
                        j1.receber_mensagem("\n--- Revanche aceita por ambos! Preparando nova partida... ---")
                        j2.receber_mensagem("\n--- Revanche aceita por ambos! Preparando nova partida... ---")
                    except Exception:
                        pass
                    # Alterna quem começa a próxima partida para justiça do jogo
                    inicio_rodada = 1 - inicio_rodada
                    continue
                else:
                    if not resp1 and not resp2:
                        motivo = "ambos os jogadores recusaram a revanche."
                    elif not resp1:
                        motivo = f"o jogador '{nome1}' recusou a revanche."
                    else:
                        motivo = f"o jogador '{nome2}' recusou a revanche."

                    msg_encerramento = (
                        f"\nPartida encerrada: {motivo}\n"
                        f"Placar Final -> {nome1} {placar[nome1]} x {placar[nome2]} {nome2} (Empates: {placar['empates']})\n"
                        f"Obrigado por jogar!"
                    )
                    try: j1.receber_mensagem(msg_encerramento)
                    except: pass
                    try: j2.receber_mensagem(msg_encerramento)
                    except: pass
                    try: j1.finalizar()
                    except: pass
                    try: j2.finalizar()
                    except: pass
                    break

        except Exception as e:
            print(f"[ERRO] Erro inesperado durante a partida: {e}")
            try: j1.finalizar()
            except: pass
            try: j2.finalizar()
            except: pass
        finally:
            # Libera os proxies e fecha sockets para evitar vazamento de memória e threads zumbis
            try: j1._pyroRelease()
            except: pass
            try: j2._pyroRelease()
            except: pass
            print(f"[SISTEMA] Recursos da partida entre '{nome1}' e '{nome2}' limpos da memória.")

def main():
    # Inicialização do middleware RPC
    daemon = Pyro5.api.Daemon()
    ns = Pyro5.api.locate_ns()
    
    # ==========================================
    # ARQUITETURA: PADRÃO SINGLETON (Instância Única)
    # ==========================================
    # 1. Instanciamos o objeto AQUI. O __init__() é executado neste exato momento,
    # criando a self.fila que será compartilhada (em memória) por todos os clientes.
    instancia_servidor = ServidorJogo()
    
    # 2. Registramos a INSTÂNCIA já criada no Pyro.
    # O Pyro usará este mesmo objeto para todas as chamadas.
    uri = daemon.register(instancia_servidor)
    
    # Registra a URI no Servidor de Nomes global para os clientes localizarem
    ns.register("jogodavelha.servidor", uri)
    
    print("[SISTEMA] Servidor de Jogo da Velha registrado no Name Server e aguardando jogadores...")
    
    # Inicia o loop de escuta (A thread principal fica bloqueada aqui mantendo o servidor vivo)
    daemon.requestLoop()

if __name__ == "__main__":
    main()