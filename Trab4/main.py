#!/usr/bin/env python3
"""
Sistema Distribuído de Relógios Vetoriais com Pyro5.

Módulo Principal de Execução / Orquestrador.
Inicia o NameServer do Pyro5, instância 4 processos concorrentes (P1, P2, P3, P4),
executa a simulação pelo tempo configurado (default: 30 segundos),
e realiza a análise causal ao final.
"""

import os
import sys
import time
import shutil
import argparse
import threading
from typing import List

import Pyro5.api
import Pyro5.nameserver

from src.process_node import ProcessNode
from src.causal_analyzer import CausalAnalyzer

# Desabilita o aviso do Pyro5 Name Server sobre IPv6 broadcast quando executando localmente
os.environ["PYRO_LOGLEVEL"] = "WARNING"


def start_nameserver_thread(host: str = "localhost", port: int = 9090) -> threading.Thread:
    """Inicia o servidor de nomes Pyro5 (Name Server) em uma thread daemon."""
    def run_ns():
        try:
            Pyro5.nameserver.start_ns_loop(host=host, port=port)
        except Exception as e:
            print(f"⚠️ Aviso no Name Server: {e}")

    ns_thread = threading.Thread(target=run_ns, daemon=True, name="Pyro-NameServer")
    ns_thread.start()
    
    # Aguarda o Name Server estar acessível
    time.sleep(1.2)
    return ns_thread


def clean_logs_directory(log_dir: str = "logs"):
    """Limpa o diretório de logs para garantir uma simulação limpa."""
    if os.path.exists(log_dir):
        try:
            shutil.rmtree(log_dir)
        except Exception:
            pass
    os.makedirs(log_dir, exist_ok=True)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Simulação Distribuída de Relógios Vetoriais com Python e Pyro5."
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Duração da simulação em segundos (Padrão: 30.0s)"
    )
    parser.add_argument(
        "--num-processes",
        type=int,
        default=4,
        help="Número de processos concorrentes (Padrão: 4 -> P1, P2, P3, P4)"
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=0.3,
        help="Atraso mínimo de envio de mensagem em segundos (Padrão: 0.3s)"
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=1.5,
        help="Atraso máximo de envio de mensagem em segundos (Padrão: 1.5s)"
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=1.2,
        help="Intervalo mínimo entre geração de eventos locais (Padrão: 1.2s)"
    )
    parser.add_argument(
        "--max-interval",
        type=float,
        default=2.5,
        help="Intervalo máximo entre geração de eventos locais (Padrão: 2.5s)"
    )
    parser.add_argument(
        "--ns-port",
        type=int,
        default=9090,
        help="Porta do Pyro5 Name Server (Padrão: 9090)"
    )
    parser.add_argument(
        "--no-analyze",
        action="store_true",
        help="Desativa a impressão automática do relatório causal no final"
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    process_ids = [f"P{i+1}" for i in range(args.num_processes)]

    print("\n" + "=" * 80)
    print("🚀 SISTEMA DISTRIBUÍDO DE RELÓGIOS VETORIAIS (PYRO5)")
    print("=" * 80)
    print(f"• Processos concorrentes: {', '.join(process_ids)}")
    print(f"• Duração da simulação  : {args.duration} segundos")
    print(f"• Atraso de rede simulado: {args.min_delay}s a {args.max_delay}s")
    print(f"• Gerador de eventos     : {args.min_interval}s a {args.max_interval}s")
    print("=" * 80 + "\n")

    # 1. Limpa logs anteriores
    clean_logs_directory()

    # 2. Inicia o Pyro5 Name Server
    print("🔄 Iniciando Pyro5 Name Server...")
    start_nameserver_thread(host="localhost", port=args.ns_port)
    print("✅ Pyro5 Name Server ativo!\n")

    # 3. Cria e registra os nós de processo (P1, P2, P3, P4)
    nodes: List[ProcessNode] = []
    print("⚙️ Inicializando os processos concorrentes e servidores RPC...")
    for pid in process_ids:
        node = ProcessNode(
            process_id=pid,
            all_process_ids=process_ids,
            ns_host="localhost",
            ns_port=args.ns_port,
            min_delay=args.min_delay,
            max_delay=args.max_delay,
            min_interval=args.min_interval,
            max_interval=args.max_interval
        )
        node.start_rpc_server()
        nodes.append(node)
        print(f"  - Processo {pid} registrado e escutando chamadas Pyro5.")

    time.sleep(1.0)
    print("\n▶️ Iniciando geração e disseminação de eventos (30 segundos)...\n")

    # 4. Inicia as threads de simulação para cada processo
    sim_threads: List[threading.Thread] = []
    for node in nodes:
        t = threading.Thread(
            target=node.run_simulation,
            args=(args.duration,),
            name=f"Worker-{node.process_id}"
        )
        t.start()
        sim_threads.append(t)

    # Aguarda a duração total da simulação
    start_time = time.time()
    try:
        while time.time() - start_time < args.duration:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n⚠️ Interrupção manual solicitada pelo usuário. Encerrando...")

    # 5. Finaliza todos os processos
    print("\n🛑 Tempo concluído. Encerrando simulação e serviços RPC...")
    for node in nodes:
        node.stop()

    for t in sim_threads:
        t.join(timeout=2.0)

    print("✅ Todos os processos foram encerrados com sucesso.")

    # Aguarda gravações de logs terminarem
    time.sleep(0.5)

    # 6. Executa a Análise Causal e Relatório de Eventos Concorrentes
    if not args.no_analyze:
        analyzer = CausalAnalyzer(json_log_path="logs/events_log.json")
        analyzer.print_report()


if __name__ == "__main__":
    main()
