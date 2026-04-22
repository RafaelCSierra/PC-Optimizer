# PC Optimizer

Aplicativo desktop com interface gráfica para Windows 11 que expõe tarefas avançadas de manutenção do sistema (CHKDSK, SFC, DISM, limpeza) e um fluxo guiado de debloat — sem precisar abrir um prompt elevado e digitar comandos manualmente.

## Funcionalidades (v1.0 / MVP)

- **System Tools:** CHKDSK, SFC, DISM (Check/Scan/RestoreHealth) e utilitários de rede (flush DNS, reset Winsock/TCP-IP).
- **Debloat Windows 11:** remoção de apps pré-instalados, presets (Mínimo / Recomendado / Agressivo) e desativação de telemetria.
- **Limpeza:** temp files, cache do Windows Update, prefetch, component store cleanup, lixeira.
- **Info do Sistema:** CPU, RAM, GPU, disco, versão do Windows, uptime.

## Segurança

Todas as operações destrutivas passam por três camadas:
1. Criação de ponto de restauração do Windows antes da execução.
2. Modo **dry-run** global — permite ver o que seria feito sem executar.
3. Confirmação dupla com checkbox "Entendo os riscos".

## Requisitos

- Windows 11 (Windows 10 deve funcionar, não testado).
- Python 3.12+ (desenvolvido em 3.14).
- Privilégios de Administrador (o app solicita UAC ao abrir).

## Como rodar em desenvolvimento

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py pc_optimizer.py
```

> **Aviso:** o app pedirá elevação via UAC. Sem elevação, comandos como `sfc /scannow` e `DISM` falharão.

## Estrutura

```
src/
  core/       # admin, executor, logger, restore_point, dry_run
  features/   # system_tools, debloat, cleanup, system_info
  ui/         # janela principal, abas, componentes
  utils/      # config, constants
```

## Licença

Uso interno. Código proprietário.
