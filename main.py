"""
Criação das máquinas virtuais do laboratório WebServer (cliente + server)
Disciplina: Development Tools & Cloud Computing

Requisitos:
  - Windows 11 com VirtualBox 7.1 ou mais novo
  - ISO do Ubuntu Desktop 24.04.1 LTS já baixada
  - Python 3.10+ (só biblioteca padrão)

Uso (no PowerShell ou no Prompt de Comando, não no IDLE):
  python criar_vms.py
"""

import getpass
import logging
import shutil
import subprocess
import sys
from pathlib import Path

# ============================================================
# CONFIGURAÇÃO
# ============================================================

# Caminho da ISO do Ubuntu (ajuste se você salvou em outro lugar)
ISO_UBUNTU = Path.home() / "Downloads" / "ubuntu-24.04.1-desktop-amd64.iso"

# Pasta padrão onde o VirtualBox guarda as VMs no Windows
PASTA_VMS = Path.home() / "VirtualBox VMs"

# Rede NAT compartilhada: as duas VMs se enxergam (ping) e têm internet (apt)
REDE_NAT = "LabWeb"
FAIXA_REDE = "10.0.2.0/24"

# Configuração mínima por limitação de hardware.
# Os discos são dinâmicos: ocupam no HD só o que for realmente usado.
VMS = [
    {
        "nome": "server",
        "usuario": "server",
        "hostname": "vm-server.lab.local",
        "memoria_mb": 2048,
        "cpus": 1,
        "vram_mb": 64,
        "disco_mb": 40960,  # 40 GB
    },
    {
        "nome": "cliente",
        "usuario": "cliente",
        "hostname": "vm-cliente.lab.local",
        "memoria_mb": 2048,
        "cpus": 1,
        "vram_mb": 64,
        "disco_mb": 20480,  # 20 GB
    },
]

# ============================================================
# LOGS
# ============================================================

ARQUIVO_LOG = Path(__file__).with_name("criacao_vms.log")

log = logging.getLogger("criar_vms")
log.setLevel(logging.DEBUG)
_formato = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%d/%m/%Y %H:%M:%S")

# Terminal: mostra os comandos e o andamento
_console = logging.StreamHandler(sys.stdout)
_console.setLevel(logging.INFO)
_console.setFormatter(_formato)

# Arquivo: guarda também a saída completa de cada comando
_arquivo = logging.FileHandler(ARQUIVO_LOG, encoding="utf-8")
_arquivo.setLevel(logging.DEBUG)
_arquivo.setFormatter(_formato)

log.addHandler(_console)
log.addHandler(_arquivo)

VBOX = ""  # caminho do VBoxManage.exe, preenchido no main()


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def localizar_vboxmanage() -> str:
    """Procura o VBoxManage no PATH ou na pasta padrão de instalação do Windows."""
    caminho = shutil.which("VBoxManage")
    if caminho:
        return caminho
    padrao = Path(r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe")
    if padrao.exists():
        return str(padrao)
    log.error("VBoxManage não encontrado. O VirtualBox está instalado?")
    sys.exit(1)


def executar(args: list[str], segredo: str | None = None) -> str:
    """Executa um comando do VBoxManage, registra no log e devolve a saída."""
    # Monta o texto do comando para o log, escondendo a senha
    exibicao = []
    for i, arg in enumerate(args):
        if i > 0 and args[i - 1] == "--password":
            exibicao.append("********")
        else:
            exibicao.append(f'"{arg}"' if " " in arg else arg)
    log.info("Executando: VBoxManage %s", " ".join(exibicao))

    resultado = subprocess.run(
        [VBOX, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    saida = (resultado.stdout + resultado.stderr).strip()
    if segredo:
        saida = saida.replace(segredo, "********")

    for linha in saida.splitlines():
        log.debug("    > %s", linha)

    if resultado.returncode != 0:
        log.error("Comando falhou (código %s):\n%s", resultado.returncode, saida)
        log.error("Se uma VM ficou pela metade, apague com: VBoxManage unregistervm <nome> --delete")
        sys.exit(1)

    log.info("OK")
    return resultado.stdout


def existe_vm(nome: str) -> bool:
    """Verifica se já existe uma VM registrada com esse nome."""
    return f'"{nome}"' in executar(["list", "vms"])


def pedir_senha() -> str:
    """Pede a senha dos usuários sem exibir no terminal (nem no código, nem no log)."""
    while True:
        senha = getpass.getpass("Senha para os usuários 'cliente' e 'server': ")
        confirmacao = getpass.getpass("Confirme a senha: ")
        if senha and senha == confirmacao:
            return senha
        print("As senhas não conferem ou estão vazias. Tente de novo.\n")


# ============================================================
# ETAPAS
# ============================================================

def criar_rede_nat() -> None:
    """Cria a Rede NAT usada pelas duas VMs (ou reaproveita se já existir)."""
    log.info("=== Rede NAT '%s' ===", REDE_NAT)
    if REDE_NAT in executar(["natnetwork", "list"]):
        log.info("Rede NAT já existe, reaproveitando.")
        return

    # Rede NAT com DHCP: cada VM recebe um IP da faixa automaticamente
    executar([
        "natnetwork", "add",
        "--netname", REDE_NAT,
        "--network", FAIXA_REDE,
        "--enable",
        "--dhcp", "on",
    ])


def criar_vm(vm: dict) -> None:
    """Cria a VM, configura o hardware, a rede e o armazenamento."""
    nome = vm["nome"]
    disco = PASTA_VMS / nome / f"{nome}.vdi"
    log.info("=== Criando a VM '%s' ===", nome)

    # 1. Cria a VM e registra no VirtualBox, com o perfil "Ubuntu 64 bits"
    executar([
        "createvm",
        "--name", nome,
        "--ostype", "Ubuntu_64",
        "--basefolder", str(PASTA_VMS),
        "--register",
    ])

    # 2. Hardware (configuração mínima)
    executar([
        "modifyvm", nome,
        "--memory", str(vm["memoria_mb"]),   # memória RAM em MB
        "--cpus", str(vm["cpus"]),           # quantidade de núcleos do processador
        "--vram", str(vm["vram_mb"]),        # memória de vídeo em MB
        "--graphicscontroller", "vmsvga",    # controladora de vídeo indicada para Linux
        "--audio-enabled", "off",            # sem áudio, para economizar recursos
        "--boot1", "dvd",                    # 1º boot pelo DVD (instalação)
        "--boot2", "disk",                   # depois pelo disco (sistema instalado)
        "--boot3", "none",
        "--boot4", "none",
    ])

    # 3. Placa de rede 1 conectada à Rede NAT compartilhada
    executar([
        "modifyvm", nome,
        "--nic1", "natnetwork",
        "--nat-network1", REDE_NAT,
    ])

    # 4. Cria o disco virtual (VDI dinamicamente alocado)
    executar([
        "createmedium", "disk",
        "--filename", str(disco),
        "--size", str(vm["disco_mb"]),       # tamanho máximo em MB
        "--format", "VDI",
        "--variant", "Standard",             # Standard = dinâmico
    ])

    # 5. Adiciona uma controladora SATA para o disco e o DVD
    executar([
        "storagectl", nome,
        "--name", "SATA",
        "--add", "sata",
        "--controller", "IntelAhci",
    ])

    # 6. Conecta o disco virtual na porta 0 da controladora
    executar([
        "storageattach", nome,
        "--storagectl", "SATA",
        "--port", "0",
        "--device", "0",
        "--type", "hdd",
        "--medium", str(disco),
    ])

    # 7. Coloca a ISO do Ubuntu no drive de DVD (porta 1)
    executar([
        "storageattach", nome,
        "--storagectl", "SATA",
        "--port", "1",
        "--device", "0",
        "--type", "dvddrive",
        "--medium", str(ISO_UBUNTU),
    ])


def configurar_instalacao(vm: dict, senha: str) -> None:
    """Prepara a instalação automática do Ubuntu (cria o usuário, idioma e fuso)."""
    nome = vm["nome"]
    log.info("=== Preparando instalação automática do Ubuntu em '%s' ===", nome)

    # A instalação começa sozinha quando a VM for ligada
    executar([
        "unattended", "install", nome,
        "--iso", str(ISO_UBUNTU),
        "--user", vm["usuario"],             # usuário pedido no trabalho
        "--password", senha,
        "--full-user-name", vm["usuario"],
        "--hostname", vm["hostname"],        # o VirtualBox exige nome com domínio
        "--locale", "pt_BR",
        "--country", "BR",
        "--time-zone", "America/Sao_Paulo",
        "--install-additions",               # Guest Additions (ajuste de tela, etc.)
    ], segredo=senha)


def ligar_vm(nome: str) -> None:
    """Liga a VM com janela, para acompanhar e tirar os prints da instalação."""
    log.info("=== Ligando a VM '%s' ===", nome)
    executar(["startvm", nome, "--type", "gui"])


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main() -> None:
    global VBOX

    log.info("Início da execução. Log completo em: %s", ARQUIVO_LOG)

    # Verificações iniciais
    VBOX = localizar_vboxmanage()
    log.info("VBoxManage encontrado em: %s", VBOX)
    log.info("Versão do VirtualBox: %s", executar(["--version"]).strip())

    if not ISO_UBUNTU.exists():
        log.error("ISO não encontrada: %s", ISO_UBUNTU)
        log.error("Ajuste a variável ISO_UBUNTU no início do script.")
        sys.exit(1)
    log.info("ISO encontrada: %s", ISO_UBUNTU)

    senha = pedir_senha()

    criar_rede_nat()

    # Cria cada VM (pula as que já existirem)
    criadas = []
    for vm in VMS:
        if existe_vm(vm["nome"]):
            log.warning("A VM '%s' já existe, pulando.", vm["nome"])
            log.warning("Para recriar: VBoxManage unregistervm %s --delete", vm["nome"])
            continue
        criar_vm(vm)
        configurar_instalacao(vm, senha)
        criadas.append(vm)

    # Resumo das configurações (útil para o relatório)
    log.info("=== Resumo ===")
    for vm in VMS:
        log.info(
            "%-8s | usuário: %-8s | RAM: %d MB | CPUs: %d | disco: %d GB | rede: %s",
            vm["nome"], vm["usuario"], vm["memoria_mb"], vm["cpus"],
            vm["disco_mb"] // 1024, REDE_NAT,
        )

    # Liga só uma VM por vez, por limitação de hardware
    for vm in criadas:
        resposta = input(f"\nLigar a VM '{vm['nome']}' agora? [s/N] ").strip().lower()
        if resposta == "s":
            ligar_vm(vm["nome"])
            log.info("Espere a instalação terminar antes de ligar a próxima VM.")
            log.info("A próxima pode ser ligada depois pelo próprio VirtualBox (botão Iniciar).")
            break

    log.info("Fim da execução.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Execução interrompida pelo usuário.")
        sys.exit(1)