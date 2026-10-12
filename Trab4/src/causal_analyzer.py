import os
import json
from typing import List, Dict, Any, Tuple
from src.vector_clock import VectorClock

# Cores para relatório de análise
COLOR_HEADER = "\033[95m\033[1m"
COLOR_CONCURRENT = "\033[93m\033[1m"  # Amarelo negrito
COLOR_PRECEDES = "\033[94m"          # Azul
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[92m"


class CausalAnalyzer:
    """
    Analisador Causal pós-execução.
    Lê os arquivos de log estruturados e identifica a ordem causal e eventos concorrentes.
    """

    def __init__(self, json_log_path: str = "logs/events_log.json"):
        self.json_log_path = json_log_path
        self.events: List[Dict[str, Any]] = []

    def load_events(self) -> bool:
        if not os.path.exists(self.json_log_path):
            print(f"❌ Arquivo de log {self.json_log_path} não encontrado.")
            return False

        try:
            with open(self.json_log_path, "r", encoding="utf-8") as f:
                self.events = json.load(f)
            # Ordena os eventos por timestamp de ocorrência (epoch)
            self.events.sort(key=lambda x: x["timestamp_epoch"])
            return True
        except Exception as e:
            print(f"❌ Erro ao ler {self.json_log_path}: {e}")
            return False

    def analyze(self) -> Dict[str, Any]:
        """
        Analisa todos os pares de eventos para identificar causalidade e concorrência.
        """
        if not self.events:
            if not self.load_events():
                return {}

        n = len(self.events)
        precedes_pairs = []
        concurrent_pairs = []
        equal_pairs = []

        # Compara cada par de eventos (i, j) com i < j
        for i in range(n):
            for j in range(i + 1, n):
                e1 = self.events[i]
                e2 = self.events[j]

                rel = VectorClock.compare(e1["vector_clock"], e2["vector_clock"])

                pair_info = {
                    "e1_id": f"{e1['process_id']}#evt{e1['event_number']}",
                    "e1_type": e1["event_type"],
                    "e1_clock": e1["vector_clock_str"],
                    "e2_id": f"{e2['process_id']}#evt{e2['event_number']}",
                    "e2_type": e2["event_type"],
                    "e2_clock": e2["vector_clock_str"],
                    "relation": rel
                }

                if rel == "PRECEDES":
                    precedes_pairs.append(pair_info)
                elif rel == "SUCCEEDS":
                    # Inverte para representação e1 precede e2 se rel==SUCCEEDS
                    pair_info["relation"] = "PRECEDES"
                    pair_info["e1_id"], pair_info["e2_id"] = pair_info["e2_id"], pair_info["e1_id"]
                    pair_info["e1_clock"], pair_info["e2_clock"] = pair_info["e2_clock"], pair_info["e1_clock"]
                    precedes_pairs.append(pair_info)
                elif rel == "CONCURRENT":
                    concurrent_pairs.append(pair_info)
                elif rel == "EQUAL":
                    equal_pairs.append(pair_info)

        return {
            "total_events": n,
            "precedes_count": len(precedes_pairs),
            "concurrent_count": len(concurrent_pairs),
            "concurrent_pairs": concurrent_pairs,
            "precedes_pairs": precedes_pairs
        }

    def print_report(self):
        """Imprime um relatório detalhado e formatado da análise causal no terminal."""
        if not self.load_events():
            return

        analysis = self.analyze()
        total = analysis["total_events"]
        conc_pairs = analysis["concurrent_pairs"]

        print("\n" + "=" * 80)
        print(f"{COLOR_HEADER}📊 RELATÓRIO DE ANÁLISE CAUSAL E CONCORRÊNCIA (RELÓGIOS VETORIAIS){COLOR_RESET}")
        print("=" * 80)
        print(f"Total de eventos registrados: {COLOR_BOLD}{total}{COLOR_RESET}")
        print(f"Pares de eventos concorrentes encontrados (E1 || E2): {COLOR_CONCURRENT}{len(conc_pairs)}{COLOR_RESET}")
        print("-" * 80)

        # 1. Tabela resumida dos eventos
        print(f"\n{COLOR_BOLD}📋 LISTA DE EVENTOS REGISTRADOS NO SISTEMA:{COLOR_RESET}")
        print(f"{'Proc':<6} | {'Evt#':<5} | {'Tipo':<8} | {'Horário':<12} | {'Relógio Vetorial':<24} | {'Detalhes'}")
        print("-" * 80)

        for ev in self.events:
            print(
                f"{ev['process_id']:<6} | "
                f"{ev['event_number']:<5} | "
                f"{ev['event_type']:<8} | "
                f"{ev['timestamp_iso']:<12} | "
                f"{ev['vector_clock_str']:<24} | "
                f"{ev['details'][:35]}"
            )

        # 2. Exibição detalhada dos eventos concorrentes (requisito central!)
        print("\n" + "=" * 80)
        print(f"{COLOR_CONCURRENT}⚡ DETECÇÃO DE EVENTOS CONCORRENTES (E1 || E2){COLOR_RESET}")
        print("Eventos concorrentes ocorrem quando nenhum relógio vetorial é estritamente menor que o outro.")
        print("=" * 80)

        if not conc_pairs:
            print("Nenhum par de eventos concorrentes foi detectado na simulação.")
        else:
            for idx, pair in enumerate(conc_pairs, 1):
                print(
                    f"{COLOR_BOLD}[Par #{idx}]{COLOR_RESET} "
                    f"{COLOR_CONCURRENT}{pair['e1_id']}{COLOR_RESET} {pair['e1_clock']} "
                    f" {COLOR_BOLD}||{COLOR_RESET} "
                    f"{COLOR_CONCURRENT}{pair['e2_id']}{COLOR_RESET} {pair['e2_clock']}"
                )

        print("\n" + "=" * 80)
        print(f"{COLOR_GREEN}✅ Análise concluída com sucesso!{COLOR_RESET}\n")
