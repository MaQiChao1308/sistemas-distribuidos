#!/usr/bin/env python3
"""
Utilitário CLI independente para ler os logs salvos em logs/events_log.json
e executar a análise causal e detecção de eventos concorrentes.
"""

import sys
from src.causal_analyzer import CausalAnalyzer

def main():
    log_file = "logs/events_log.json"
    if len(sys.argv) > 1:
        log_file = sys.argv[1]

    analyzer = CausalAnalyzer(json_log_path=log_file)
    analyzer.print_report()

if __name__ == "__main__":
    main()
