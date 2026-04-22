"""Windows services: catálogo curado de serviços 'opcionais' e toggles Start/Stop/Type.

O catálogo lista serviços que a maioria dos usuários pode mexer sem quebrar o
sistema principal — mas cada um tem `impact` explicando o que se perde ao
desabilitar, para a UI poder avisar antes.

As operações (Set-Service / Stop-Service / Start-Service) são feitas via
PowerShell em subprocess. Todas requerem privilégios de Administrador.
"""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass

_CREATE_NO_WINDOW = 0x08000000
_log = logging.getLogger("pc_optimizer.services")


# PowerShell StartType values: Automatic, Manual, Disabled, AutomaticDelayedStart
STARTUP_LABELS = {
    "Automatic": "Automático",
    "Manual": "Manual",
    "Disabled": "Desabilitado",
    "AutomaticDelayedStart": "Automático (atraso)",
}


@dataclass(frozen=True)
class OptionalService:
    service_name: str       # short name (e.g. "DiagTrack")
    display_name: str       # user-facing
    description: str        # what the service does
    impact: str             # what you lose if you disable
    default_startup: str    # Windows default — used when "Restaurar" clicked


OPTIONAL_SERVICES: tuple[OptionalService, ...] = (
    OptionalService(
        service_name="DiagTrack",
        display_name="Connected User Experiences and Telemetry",
        description="Coleta diagnósticos e telemetria para enviar à Microsoft.",
        impact="Desabilitar reduz drasticamente a coleta. Algumas tasks de diagnóstico ficam inativas — impacto baixo para o usuário comum.",
        default_startup="Automatic",
    ),
    OptionalService(
        service_name="SysMain",
        display_name="SysMain (antigo Superfetch)",
        description="Pré-carrega apps frequentes para acelerar abertura.",
        impact="Em SSDs o ganho é mínimo e desabilitar é seguro. Em HDDs boot/abertura de apps podem ficar ligeiramente mais lentos.",
        default_startup="Automatic",
    ),
    OptionalService(
        service_name="WSearch",
        display_name="Windows Search",
        description="Indexa arquivos para a busca instantânea do Windows.",
        impact="Desabilitar torna a busca por nome MUITO mais lenta. Só desabilite se usa outra ferramenta (Everything, etc).",
        default_startup="Automatic",
    ),
    OptionalService(
        service_name="XblAuthManager",
        display_name="Xbox Live Auth Manager",
        description="Autenticação Xbox Live para apps e jogos.",
        impact="Sem impacto para quem não usa Xbox. Pode quebrar login em jogos PC Game Pass.",
        default_startup="Manual",
    ),
    OptionalService(
        service_name="XblGameSave",
        display_name="Xbox Live Game Save",
        description="Sincroniza saves de jogos Xbox com a nuvem.",
        impact="Sem impacto para quem não joga com conta Xbox ligada.",
        default_startup="Manual",
    ),
    OptionalService(
        service_name="XboxNetApiSvc",
        display_name="Xbox Live Networking Service",
        description="Comunicação de rede multiplayer Xbox Live.",
        impact="Sem impacto para quem não joga jogos Xbox Live no PC.",
        default_startup="Manual",
    ),
    OptionalService(
        service_name="XboxGipSvc",
        display_name="Xbox Accessory Management Service",
        description="Gerencia controles e acessórios Xbox conectados ao PC.",
        impact="Desabilitar quebra controles Xbox (USB e wireless) no PC.",
        default_startup="Manual",
    ),
    OptionalService(
        service_name="lfsvc",
        display_name="Geolocation Service",
        description="Permite apps acessarem sua localização (GPS/Wi-Fi/IP).",
        impact="Apps como Mapas, Clima e assistentes perdem acesso à localização.",
        default_startup="Manual",
    ),
    OptionalService(
        service_name="Spooler",
        display_name="Print Spooler",
        description="Gerencia a fila de impressão.",
        impact="Desabilitar impede qualquer impressão. Seguro SE você não usa impressora.",
        default_startup="Automatic",
    ),
    OptionalService(
        service_name="Fax",
        display_name="Fax",
        description="Envio e recebimento de fax via modem/servidor.",
        impact="Praticamente ninguém usa. Seguro desabilitar.",
        default_startup="Manual",
    ),
    OptionalService(
        service_name="bthserv",
        display_name="Bluetooth Support Service",
        description="Suporte a dispositivos Bluetooth.",
        impact="Desabilitar quebra TODOS os dispositivos Bluetooth (fone, mouse, teclado).",
        default_startup="Manual",
    ),
    OptionalService(
        service_name="RemoteRegistry",
        display_name="Remote Registry",
        description="Permite edição remota do registry por outros PCs.",
        impact="Normalmente já vem desabilitado por padrão de segurança.",
        default_startup="Disabled",
    ),
    OptionalService(
        service_name="WerSvc",
        display_name="Windows Error Reporting Service",
        description="Envia relatórios de crash/erro para a Microsoft.",
        impact="Desabilitar reduz telemetria sem afetar o uso.",
        default_startup="Manual",
    ),
    OptionalService(
        service_name="TabletInputService",
        display_name="Touch Keyboard and Handwriting Panel Service",
        description="Teclado virtual e reconhecimento de escrita à mão.",
        impact="Sem impacto em desktops sem tela touch.",
        default_startup="Manual",
    ),
    OptionalService(
        service_name="MapsBroker",
        display_name="Downloaded Maps Manager",
        description="Gerencia mapas offline do app Mapas.",
        impact="Sem impacto para quem não usa o app Mapas do Windows.",
        default_startup="Automatic",
    ),
)


_PS = ("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command")


def _run(script: str, timeout: float = 15.0) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            list(_PS) + [script],
            capture_output=True, text=True, timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"
    except FileNotFoundError:
        return 1, "", "powershell não encontrado"
    return r.returncode, r.stdout or "", r.stderr or ""


def get_state(service_name: str) -> tuple[str, str] | None:
    """Return (StartType, Status) or None if service not found / failure.

    StartType: "Automatic" | "Manual" | "Disabled" | "AutomaticDelayedStart"
    Status:    "Running" | "Stopped" | ...
    """
    safe = service_name.replace("'", "''")
    script = (
        f"try {{ "
        f"$s = Get-Service -Name '{safe}' -ErrorAction Stop; "
        f"@{{ StartType = $s.StartType.ToString(); Status = $s.Status.ToString() }} "
        f"| ConvertTo-Json -Compress "
        f"}} catch {{ 'NOT_FOUND' }}"
    )
    code, out, err = _run(script)
    if code != 0:
        _log.debug("get_state %s failed: %s", service_name, err.strip())
        return None
    out = out.strip()
    if not out or out == "NOT_FOUND":
        return None
    try:
        data = json.loads(out)
        return (str(data.get("StartType")), str(data.get("Status")))
    except json.JSONDecodeError:
        return None


def set_startup_type(service_name: str, startup: str) -> tuple[bool, str]:
    """Set the service's StartupType. Stops the service first if setting Disabled."""
    if startup not in STARTUP_LABELS:
        return False, f"valor inválido: {startup}"
    safe = service_name.replace("'", "''")
    stop_block = ""
    if startup == "Disabled":
        stop_block = (
            f"if ((Get-Service -Name '{safe}').Status -eq 'Running') "
            f"{{ Stop-Service -Name '{safe}' -Force -ErrorAction SilentlyContinue }}; "
        )
    script = (
        "try { "
        f"{stop_block}"
        f"Set-Service -Name '{safe}' -StartupType {startup} -ErrorAction Stop; "
        "'OK' "
        "} catch { $_.Exception.Message }"
    )
    code, out, err = _run(script, timeout=30)
    result = (out or err).strip()
    if code == 0 and result.endswith("OK"):
        return True, f"{service_name}: {STARTUP_LABELS[startup]}"
    return False, f"erro: {result[:200]}"
