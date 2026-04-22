"""Catalog of Windows maintenance commands surfaced in the System Tools tab."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"      # read-only, no system change
    LOW = "low"        # reversible changes, runs online
    MEDIUM = "medium"  # requires reboot OR pauses core services
    HIGH = "high"      # significant system impact

    @property
    def label(self) -> str:
        return {
            RiskLevel.SAFE: "Seguro",
            RiskLevel.LOW: "Baixo",
            RiskLevel.MEDIUM: "Médio",
            RiskLevel.HIGH: "Alto",
        }[self]

    @property
    def color(self) -> str:
        return {
            RiskLevel.SAFE: "#2ea043",
            RiskLevel.LOW: "#3fb950",
            RiskLevel.MEDIUM: "#d29922",
            RiskLevel.HIGH: "#f85149",
        }[self]


@dataclass(frozen=True)
class SystemTask:
    id: str
    label: str
    description: str
    cmd: str
    risk: RiskLevel
    needs_reboot: bool = False
    long_running: bool = False


SYSTEM_TASKS: tuple[SystemTask, ...] = (
    # --- CHKDSK ---
    SystemTask(
        id="chkdsk_verify",
        label="CHKDSK — Verificar disco C:",
        description=(
            "Varredura read-only do volume C:. Informa erros sem alterar nada. "
            "Bom primeiro diagnóstico."
        ),
        cmd="chkdsk C:",
        risk=RiskLevel.SAFE,
    ),
    SystemTask(
        id="chkdsk_scan",
        label="CHKDSK — Reparar online (/scan)",
        description=(
            "Escaneia e repara erros que podem ser corrigidos online, sem reiniciar. "
            "Pode levar alguns minutos."
        ),
        cmd="chkdsk C: /scan",
        risk=RiskLevel.LOW,
        long_running=True,
    ),
    SystemTask(
        id="chkdsk_fix_reboot",
        label="CHKDSK — Agendar reparo completo (/f /r)",
        description=(
            "Agenda varredura completa do disco no próximo boot. Corrige erros de "
            "sistema de arquivos e setores defeituosos. Requer reinicialização."
        ),
        cmd="chkdsk C: /f /r",
        risk=RiskLevel.MEDIUM,
        needs_reboot=True,
        long_running=True,
    ),
    # --- SFC ---
    SystemTask(
        id="sfc_verifyonly",
        label="SFC — Verificar apenas",
        description="System File Checker em modo read-only: reporta corrupção sem reparar.",
        cmd="sfc /verifyonly",
        risk=RiskLevel.SAFE,
        long_running=True,
    ),
    SystemTask(
        id="sfc_scannow",
        label="SFC — Escanear e reparar",
        description=(
            "Verifica integridade de arquivos de sistema e substitui versões "
            "corrompidas pelo cache local."
        ),
        cmd="sfc /scannow",
        risk=RiskLevel.LOW,
        long_running=True,
    ),
    # --- DISM ---
    SystemTask(
        id="dism_check",
        label="DISM — CheckHealth",
        description="Checagem rápida por flags de corrupção na imagem do Windows.",
        cmd="DISM /Online /Cleanup-Image /CheckHealth",
        risk=RiskLevel.SAFE,
    ),
    SystemTask(
        id="dism_scan",
        label="DISM — ScanHealth",
        description="Varredura completa da imagem do Windows em busca de corrupção. Mais lenta.",
        cmd="DISM /Online /Cleanup-Image /ScanHealth",
        risk=RiskLevel.SAFE,
        long_running=True,
    ),
    SystemTask(
        id="dism_restore",
        label="DISM — RestoreHealth",
        description=(
            "Repara a imagem do Windows usando arquivos do Windows Update. Pode "
            "levar 15+ minutos. Recomendado rodar antes de SFC se ScanHealth apontar problemas."
        ),
        cmd="DISM /Online /Cleanup-Image /RestoreHealth",
        risk=RiskLevel.LOW,
        long_running=True,
    ),
    # --- Rede ---
    SystemTask(
        id="net_flush_dns",
        label="Rede — Flush DNS",
        description="Limpa o cache do resolvedor DNS. Útil após mudar servidores DNS ou com problemas de nome.",
        cmd="ipconfig /flushdns",
        risk=RiskLevel.SAFE,
    ),
    SystemTask(
        id="net_winsock_reset",
        label="Rede — Reset Winsock",
        description=(
            "Reseta o catálogo do Winsock para o estado default. Útil em problemas "
            "de conectividade persistentes. Requer reinicialização."
        ),
        cmd="netsh winsock reset",
        risk=RiskLevel.MEDIUM,
        needs_reboot=True,
    ),
    SystemTask(
        id="net_tcpip_reset",
        label="Rede — Reset TCP/IP",
        description=(
            "Reseta a pilha TCP/IP para o estado default. Pode resolver problemas de "
            "conectividade. Requer reinicialização."
        ),
        cmd="netsh int ip reset",
        risk=RiskLevel.MEDIUM,
        needs_reboot=True,
    ),
)
