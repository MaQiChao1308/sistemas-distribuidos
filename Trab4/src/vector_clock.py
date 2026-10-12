import threading
from typing import Dict, List, Literal

RelationType = Literal["EQUAL", "PRECEDES", "SUCCEEDS", "CONCURRENT"]


class VectorClock:
    """
    Classe thread-safe que gerencia o Relógio Vetorial de um processo distribuído.
    
    Regras de Atualização:
    1. Evento Local / Envio: V_i[i] = V_i[i] + 1
    2. Recepção de Mensagem:
       - V_i[k] = max(V_i[k], V_msg[k]) para todos os processos k
       - V_i[i] = V_i[i] + 1 (para registrar o evento de recepção)
    """

    def __init__(self, process_id: str, all_process_ids: List[str]):
        self.process_id = process_id
        self.all_process_ids = sorted(all_process_ids)
        # Inicializa o relógio com zeros para todos os processos conhecidos
        self._clock: Dict[str, int] = {pid: 0 for pid in self.all_process_ids}
        self._lock = threading.Lock()

    def increment(self) -> Dict[str, int]:
        """
        Incrementa a posição local do processo no relógio vetorial.
        Retorna uma cópia do relógio atualizado.
        """
        with self._lock:
            self._clock[self.process_id] += 1
            return self._clock.copy()

    def update_on_receive(self, received_clock: Dict[str, int]) -> Dict[str, int]:
        """
        Atualiza o relógio vetorial local com base no relógio recebido em uma mensagem.
        Realiza o elemento-a-elemento max e depois incrementa o relógio local.
        Retorna uma cópia do relógio resultante.
        """
        with self._lock:
            # 1. Element-wise maximum
            for pid in self.all_process_ids:
                msg_val = received_clock.get(pid, 0)
                self._clock[pid] = max(self._clock[pid], msg_val)
            
            # 2. Incrementa o relógio local para o evento de recepção
            self._clock[self.process_id] += 1
            return self._clock.copy()

    def get_clock(self) -> Dict[str, int]:
        """Retorna uma cópia do relógio vetorial atual."""
        with self._lock:
            return self._clock.copy()

    def format_clock(self, clock_dict: Dict[str, int] = None) -> str:
        """Formata o relógio vetorial para exibição amigável [P1:x, P2:y, ...]."""
        c = clock_dict if clock_dict is not None else self.get_clock()
        items = [f"{pid}:{c.get(pid, 0)}" for pid in self.all_process_ids]
        return f"[{', '.join(items)}]"

    @staticmethod
    def compare(v1: Dict[str, int], v2: Dict[str, int]) -> RelationType:
        """
        Compara dois relógios vetoriais v1 e v2.
        
        Retorna:
        - "EQUAL": v1 == v2
        - "PRECEDES": v1 < v2 (v1 causou/antecedeu v2)
        - "SUCCEEDS": v1 > v2 (v2 causou/antecedeu v1)
        - "CONCURRENT": v1 || v2 (eventos concorrentes)
        """
        all_keys = set(v1.keys()).union(set(v2.keys()))
        
        v1_le_v2 = True
        v2_le_v1 = True
        equal = True

        for k in all_keys:
            val1 = v1.get(k, 0)
            val2 = v2.get(k, 0)

            if val1 != val2:
                equal = False
            if val1 > val2:
                v1_le_v2 = False
            if val2 > val1:
                v2_le_v1 = False

        if equal:
            return "EQUAL"
        elif v1_le_v2:
            return "PRECEDES"
        elif v2_le_v1:
            return "SUCCEEDS"
        else:
            return "CONCURRENT"
