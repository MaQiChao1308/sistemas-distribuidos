import os
import json
import time
import threading
from datetime import datetime
from typing import Dict, Any

# ANSI Color codes for terminal display
COLORS = {
    "P1": "\033[96m",   # Cyan
    "P2": "\033[92m",   # Green
    "P3": "\033[93m",   # Yellow
    "P4": "\033[95m",   # Magenta
    "SYSTEM": "\033[94m",# Blue
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
    "LOCAL": "\033[36m",  # Cyan for local events
    "SEND": "\033[34m",   # Blue for send events
    "RECEIVE": "\033[35m"# Magenta for receive events
}


class ProcessLogger:
    """
    Logger thread-safe para registrar eventos locais, envios e recepções de mensagens,
    exibindo no terminal com formatação colorida e persistindo em arquivos.
    """

    def __init__(self, process_id: str, log_dir: str = "logs"):
        self.process_id = process_id
        self.log_dir = log_dir
        self._lock = threading.Lock()
        
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file_path = os.path.join(self.log_dir, f"process_{self.process_id}.log")
        self.json_log_path = os.path.join(self.log_dir, "events_log.json")

    def _get_timestamp_str(self) -> str:
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def log_event(
        self,
        event_number: int,
        event_type: str,  # "LOCAL", "SEND", "RECEIVE"
        vector_clock_str: str,
        vector_clock_dict: Dict[str, int],
        details: str,
        sender_id: str = None
    ) -> Dict[str, Any]:
        """
        Registra um evento local ou de recepção de mensagem.
        """
        ts_str = self._get_timestamp_str()
        ts_epoch = time.time()
        color = COLORS.get(self.process_id, COLORS["SYSTEM"])
        reset = COLORS["RESET"]
        bold = COLORS["BOLD"]

        type_badge = {
            "LOCAL": "⚙️ LOCAL ",
            "SEND": "📤 ENVIO ",
            "RECEIVE": "📥 RECEB "
        }.get(event_type, event_type)

        # Formatação para o terminal
        terminal_msg = (
            f"{color}[{ts_str}] [{bold}{self.process_id:^4}{reset}{color}] "
            f"[{type_badge}] Evento #{event_number:<3} | "
            f"Relógio: {bold}{vector_clock_str:<22}{reset}{color} | {details}{reset}"
        )

        event_record = {
            "process_id": self.process_id,
            "event_number": event_number,
            "event_type": event_type,
            "timestamp_iso": ts_str,
            "timestamp_epoch": ts_epoch,
            "vector_clock": vector_clock_dict,
            "vector_clock_str": vector_clock_str,
            "details": details,
            "sender_id": sender_id
        }

        with self._lock:
            # 1. Imprime no terminal
            print(terminal_msg, flush=True)

            # 2. Salva no arquivo de log do processo (.log)
            plain_line = f"[{ts_str}] [{self.process_id}] [{event_type}] Evento #{event_number} | Relógio: {vector_clock_str} | {details}\n"
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(plain_line)

            # 3. Salva no log estruturado JSON compartilhado
            self._append_json_record(event_record)

        return event_record

    def _append_json_record(self, record: Dict[str, Any]):
        records = []
        if os.path.exists(self.json_log_path):
            try:
                with open(self.json_log_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []
        
        records.append(record)
        with open(self.json_log_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
