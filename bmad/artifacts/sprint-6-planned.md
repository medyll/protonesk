# Sprint 6 — Packaging (service Windows + systemd Linux)

**Goal:** Installer le bridge comme service système qui démarre automatiquement.

## Stories

| ID | Titre | Effort |
|----|-------|--------|
| S6-01 | Service Windows (NSSM ou pywin32) | M |
| S6-02 | Service systemd Linux | S |
| S6-03 | Script install/uninstall cross-platform | M |
| S6-04 | Tray icon Windows (optionnel) | L |

## Stories détail

### S6-01 — Service Windows

- `scripts/install-service-windows.ps1`
- Utilise NSSM (Non-Sucking Service Manager) ou `pywin32.servicemanager`
- Service name : `ProtonMailBridge`
- Start type : Automatic
- Log vers `%APPDATA%\ProtonMailBridge\bridge.log`
- Commandes : `install`, `uninstall`, `start`, `stop`, `status`

```powershell
# Usage
.\scripts\install-service-windows.ps1 install
.\scripts\install-service-windows.ps1 start
```

### S6-02 — Service systemd Linux

- `scripts/proton-bridge.service` (unit file)
- `ExecStart=/usr/local/bin/python /opt/proton-bridge/main.py`
- `Restart=on-failure`, `RestartSec=5`
- `WantedBy=multi-user.target`
- Script `scripts/install-service-linux.sh` copie unit + reload daemon

### S6-03 — Script install cross-platform

- `scripts/install.py` — détecte OS, appelle le bon installeur
- Vérifie Python >= 3.11, installe deps
- Génère `config.yaml` interactif si absent
- Lance `python src/secrets.py setup` si credentials manquants

### S6-04 — Tray icon Windows (optionnel)

- `pystray` library
- Icône dans system tray : status (connecté / déconnecté / erreur)
- Menu : Start/Stop bridge, Open config, Quit
- Notification Windows si nouvelle connexion client IMAP
- Blocker : nécessite thread séparé + compatibilité asyncio

## Contraintes

- Service doit tourner sous compte utilisateur (pas SYSTEM) pour accès keyring
- Windows : keyring nécessite session utilisateur active — service interactif requis
- Linux : keyring via `secret-service` (GNOME) ou `kwallet` — headless OK avec `gnome-keyring-daemon`
