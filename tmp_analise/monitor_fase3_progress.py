#!/usr/bin/env python3
"""
Monitor de Progresso — Fase 3 Rerotulação Minimax (NPZs 183+)
Fornece estimativa de tempo e métricas padronizadas.
"""
import os
import glob
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = r"D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\dados\profundidade_minimax_11_adaptativo"
MIN_POPULATED_SIZE_KB = 303  # Arquivo com melhor_jogada populada
MIN_PENDING_SIZE_KB = 95     # Arquivo com amostras mas sem melhor_jogada

def get_npz_files():
    """Retorna lista de NPZ files com número, tamanho e timestamp."""
    files = []
    pattern = os.path.join(DATA_DIR, "dataset_pequeno_*.npz")
    for fpath in sorted(glob.glob(pattern)):
        try:
            num = int(Path(fpath).stem.replace("dataset_pequeno_0", "").lstrip("0") or "0")
            if num >= 183:
                stat = os.stat(fpath)
                size_kb = stat.st_size / 1024
                mtime = datetime.fromtimestamp(stat.st_mtime)
                files.append({
                    'num': num,
                    'path': fpath,
                    'size_kb': size_kb,
                    'mtime': mtime
                })
        except (ValueError, OSError):
            pass
    return files

def categorize_files(files):
    """Categoriza NPZs em populados e aguardando."""
    populated = []
    pending = []
    incomplete = []

    for f in files:
        if f['size_kb'] >= MIN_POPULATED_SIZE_KB:
            populated.append(f)
        elif f['size_kb'] >= MIN_PENDING_SIZE_KB:
            pending.append(f)
        else:
            incomplete.append(f)

    return populated, pending, incomplete

def estimate_eta(populated, pending):
    """Estima tempo até conclusão baseado em velocidade recente."""
    if len(populated) < 2:
        return None, None  # Não há dados suficientes

    # Calcula velocidade usando os últimos 10 arquivos populados
    recent = populated[-10:]
    if len(recent) < 2:
        recent = populated

    time_span = recent[-1]['mtime'] - recent[0]['mtime']
    if time_span.total_seconds() <= 0:
        return None, None

    files_processed = len(recent) - 1
    if files_processed <= 0:
        return None, None

    seconds_per_file = time_span.total_seconds() / files_processed
    hours_per_file = seconds_per_file / 3600

    remaining_files = len(pending)
    hours_remaining = remaining_files * hours_per_file
    eta_datetime = datetime.now() + timedelta(hours=hours_remaining)

    return hours_remaining, eta_datetime

def format_report(populated, pending, incomplete):
    """Formata relatório padronizado."""
    total_new = len(populated) + len(pending) + len(incomplete)
    completed_pct = (len(populated) / total_new * 100) if total_new > 0 else 0

    hours_remaining, eta_datetime = estimate_eta(populated, pending)

    # Tempo decorrido desde NPZ 183
    inicio = populated[0]['mtime'] if populated else None
    now = datetime.now()
    if inicio:
        elapsed = now - inicio
        total_seconds = int(elapsed.total_seconds())
        elapsed_days = total_seconds // 86400
        elapsed_hours = (total_seconds % 86400) // 3600
        elapsed_mins = (total_seconds % 3600) // 60
        if elapsed_days > 0:
            elapsed_str = f"{elapsed_days}d {elapsed_hours:02d}h {elapsed_mins:02d}m"
        else:
            elapsed_str = f"{elapsed_hours}h {elapsed_mins:02d}m"
    else:
        elapsed_str = "N/A"
        inicio = now

    # Cabeçalho
    print("=" * 70)
    print("MONITOR DE PROGRESSO - FASE 3 REROTULACAO MINIMAX (NPZs 183+)")
    print("=" * 70)
    print(f"Atualizado em:    {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Inicio (NPZ 183): {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tempo decorrido:  {elapsed_str}")
    print()

    # Status atual
    print("STATUS ATUAL:")
    print(f"  Populados com melhor_jogada: {len(populated):3d} NPZs (NPZ {populated[0]['num']}-{populated[-1]['num']})")
    print(f"  Aguardando processamento:    {len(pending):3d} NPZs (NPZ {pending[0]['num']}-{pending[-1]['num']})")
    if incomplete:
        print(f"  Incompletos/órfãos:         {len(incomplete):3d} NPZs")
    print(f"  {'-' * 66}")
    print(f"  Total de NPZs novos:         {total_new:3d} NPZs")
    print()

    # Progresso
    print("PROGRESSO:")
    bar_filled = int(completed_pct / 5)  # 20 caracteres de barra
    bar = "#" * bar_filled + "." * (20 - bar_filled)
    print(f"  [{bar}] {completed_pct:5.1f}%")
    print()

    # ETA
    print("ESTIMATIVA DE CONCLUSAO:")
    if hours_remaining is not None and eta_datetime is not None:
        if hours_remaining < 24:
            print(f"  Tempo restante: ~{hours_remaining:.1f} horas")
            print(f"  ETA: {eta_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            days = hours_remaining / 24
            print(f"  Tempo restante: ~{days:.1f} dias ({hours_remaining:.1f} horas)")
            print(f"  ETA: {eta_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

        # Velocidade
        recent = populated[-10:] if len(populated) >= 10 else populated
        if len(recent) >= 2:
            time_span = recent[-1]['mtime'] - recent[0]['mtime']
            hours_span = time_span.total_seconds() / 3600
            if hours_span > 0:
                npz_per_hour = (len(recent) - 1) / hours_span
                print(f"  Velocidade: {npz_per_hour:.2f} NPZs/hora")
    else:
        print("  (Dados insuficientes para estimativa)")
    print()

    # Detalhes dos últimos processados
    if populated:
        print("ULTIMOS 5 NPZs PROCESSADOS:")
        for f in populated[-5:]:
            mtime_str = f['mtime'].strftime('%H:%M:%S')
            print(f"  NPZ {f['num']:3d} - {mtime_str} ({f['size_kb']:.1f} KB)")
    print()

    print("=" * 70)

if __name__ == "__main__":
    files = get_npz_files()
    populated, pending, incomplete = categorize_files(files)
    format_report(populated, pending, incomplete)
