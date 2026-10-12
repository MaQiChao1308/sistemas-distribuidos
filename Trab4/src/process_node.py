import random
import threading
import time
from typing import List, Dict, Any
import Pyro5.api

from src.vector_clock import VectorClock
from src.logger import ProcessLogger

# Exemplos de descrições de eventos locais para simulação
SAMPLE_LOCAL_TASKS = [
    "Processamento de lote de dados",
    "Atualização de índice de busca",
    "Verificação de consistência de estado",
    "Cálculo de agregação de métricas",
    "Exportação de snapshot de memória",
    "Compactação de arquivo de log",
    "Validação de assinatura digital",
    "Limpeza de cache de transações"
]


@Pyro5.api.expose
class ProcessRPC:
    """
    Interface RPC remota exposta pelo Pyro5 para receber mensagens de outros processos.
    """

    def __init__(self, node):
        self.node = node

    def receive_message(
        self,
        sender_id: str,
        msg_event_id: int,
        sender_clock: Dict[str, int],
        payload: str,
        send_timestamp: float
    ) -> None:
        """
        Método remoto invocado por outros processos quando um evento é disseminado.
        """
        self.node.handle_received_message(
            sender_id=sender_id,
            msg_event_id=msg_event_id,
            sender_clock=sender_clock,
            payload=payload,
            send_timestamp=send_timestamp
        )


class ProcessNode:
    """
    Representa um nó / processo independente no sistema distribuído ($P_1, P_2, \dots$).
    
    Cada nó possui:
    - Um Relógio Vetorial
    - Um Logger local
    - Um servidor Pyro5 Daemon para responder a chamadas RPC
    - Uma thread geradora de eventos locais e disseminadora de mensagens
    """

    def __init__(
        self,
        process_id: str,
        all_process_ids: List[str],
        ns_host: str = "localhost",
        ns_port: int = 9090,
        min_delay: float = 0.2,
        max_delay: float = 1.5,
        min_interval: float = 1.0,
        max_interval: float = 2.5,
        log_dir: str = "logs"
    ):
        self.process_id = process_id
        self.all_process_ids = sorted(all_process_ids)
        self.peers = [pid for pid in self.all_process_ids if pid != self.process_id]
        
        self.ns_host = ns_host
        self.ns_port = ns_port
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.min_interval = min_interval
        self.max_interval = max_interval

        self.vector_clock = VectorClock(self.process_id, self.all_process_ids)
        self.logger = ProcessLogger(self.process_id, log_dir=log_dir)
        self.event_counter = 0
        self._counter_lock = threading.Lock()

        self._running = False
        self._daemon = None
        self._daemon_thread = None
        self._generator_thread = None

    def start_rpc_server(self):
        """Inicia o Daemon do Pyro5 e registra este processo no Name Server."""
        self._daemon = Pyro5.api.Daemon(host="localhost")
        
        # Cria a instância RPC exposta
        rpc_instance = ProcessRPC(self)
        uri = self._daemon.register(rpc_instance)

        # Localiza o Name Server e registra o nome do processo (ex: "P1")
        ns = Pyro5.api.locate_ns(host=self.ns_host, port=self.ns_port)
        ns.register(self.process_id, uri)

        # Roda o loop do daemon em thread secundária
        self._daemon_thread = threading.Thread(
            target=self._daemon.requestLoop,
            daemon=True,
            name=f"Daemon-{self.process_id}"
        )
        self._daemon_thread.start()

    def _next_event_number(self) -> int:
        with self._counter_lock:
            self.event_counter += 1
            return self.event_counter

    def handle_received_message(
        self,
        sender_id: str,
        msg_event_id: int,
        sender_clock: Dict[str, int],
        payload: str,
        send_timestamp: float
    ):
        """
        Trata o recebimento de uma mensagem vinda de outro processo:
        1. Atualiza o relógio vetorial com as regras max(V_local, V_msg) e V_local[i]++
        2. Registra o evento de recepção no log local.
        """
        # Atualização do Relógio Vetorial
        updated_clock = self.vector_clock.update_on_receive(sender_clock)
        event_num = self._next_event_number()
        clock_str = self.vector_clock.format_clock(updated_clock)

        calc_delay = time.time() - send_timestamp
        details = (
            f"Recebido de {sender_id} (Evento #{msg_event_id} de {sender_id}). "
            f"Atraso simulado: {calc_delay:.2f}s | Conteúdo: '{payload}'"
        )

        self.logger.log_event(
            event_number=event_num,
            event_type="RECEIVE",
            vector_clock_str=clock_str,
            vector_clock_dict=updated_clock,
            details=details,
            sender_id=sender_id
        )

    def _disseminate_to_peer(
        self,
        peer_id: str,
        event_num: int,
        sender_clock: Dict[str, int],
        payload: str
    ):
        """
        Envia mensagem a um destinatário específico com um atraso simulado (time.sleep aleatório).
        Roda em uma thread separada para não bloquear o envio aos demais destinatários.
        """
        # Atraso simulado aleatório para criar ordens de entrega diferentes
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

        try:
            ns = Pyro5.api.locate_ns(host=self.ns_host, port=self.ns_port)
            peer_uri = ns.lookup(peer_id)
            with Pyro5.api.Proxy(peer_uri) as peer_proxy:
                peer_proxy.receive_message(
                    sender_id=self.process_id,
                    msg_event_id=event_num,
                    sender_clock=sender_clock,
                    payload=payload,
                    send_timestamp=time.time()
                )
        except Exception as e:
            # Em encerramentos de simulação, conexões podem fechar graciosamente
            pass

    def generate_local_event(self):
        """
        Gera um evento local no processo:
        1. Incrementa a posição do processo no relógio vetorial.
        2. Registra no log local.
        3. Envia mensagens com atrasos simulados aos outros processos.
        """
        # 1. Incrementa relógio vetorial
        updated_clock = self.vector_clock.increment()
        event_num = self._next_event_number()
        clock_str = self.vector_clock.format_clock(updated_clock)

        task_name = random.choice(SAMPLE_LOCAL_TASKS)
        details = f"Operação local '{task_name}' concluída"

        # 2. Registrar evento local
        self.logger.log_event(
            event_number=event_num,
            event_type="LOCAL",
            vector_clock_str=clock_str,
            vector_clock_dict=updated_clock,
            details=details
        )

        # 3. Disseminar mensagem para os outros processos em threads separadas (com atrasos independentes)
        for peer_id in self.peers:
            t = threading.Thread(
                target=self._disseminate_to_peer,
                args=(peer_id, event_num, updated_clock, task_name),
                daemon=True,
                name=f"Send-{self.process_id}->{peer_id}"
            )
            t.start()

    def run_simulation(self, duration: float):
        """
        Roda a geração continuada de eventos durante o período definido (ex: 30 segundos).
        """
        self._running = True
        start_time = time.time()

        while self._running and (time.time() - start_time < duration):
            # Intervalo aleatório entre geração de eventos
            interval = random.uniform(self.min_interval, self.max_interval)
            time.sleep(interval)

            if not self._running or (time.time() - start_time >= duration):
                break

            self.generate_local_event()

    def stop(self):
        """Finaliza graciosamente o nó do processo e unregister do Name Server."""
        self._running = False
        if self._daemon:
            try:
                ns = Pyro5.api.locate_ns(host=self.ns_host, port=self.ns_port)
                ns.remove(self.process_id)
            except Exception:
                pass
            self._daemon.shutdown()
