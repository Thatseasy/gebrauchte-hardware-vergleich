# Setup Doku PC

# 🚀 2026 Dev Environment Documentation

> System: Windows 11 Native (No WSL required)Core: Google Antigravity (Gemini 3 Native)Shell: PowerShell 7 + Starship
> 

# Installation

---

## Phase 1: Die Basis (Alles über `winget`)

Öffne deine PowerShell (am besten als Admin) und feuere diese Befehle ab. `winget` ist in Windows 11 integriert.

`powershell# 1. Core Tools & Antigravity IDE
winget install -e --id Google.Antigravity
winget install -e --id Git.Git
winget install -e --id Microsoft.PowerShell # Update auf PowerShell 7+

# 2. Modern Package Managers (Besser als direkte Installationen)
# fnm = Fast Node Manager (viel schneller als nvm-windows)
winget install -e --id Schniz.fnm 
# uv = Der neue Python Standard (ersetzt pip/venv/poetry für viele, extrem schnell)
winget install -e --id astral-sh.uv

# 3. "Quality of Life" & CLI Power-Tools (Rust-based replacement für alte Unix tools)
winget install -e --id Starship.Starship    # High-Performance Prompt
winget install -e --id BurntSushi.ripgrep.MSVC # Schnelleres Grep (rg)
winget install -e --id sharkdp.bat          # Besseres 'cat' mit Syntax Highlighting
winget install -e --id lsd-rs.lsd           # Besseres 'ls' mit Icons (lsd)
winget install -e --id junegunn.fzf         # Fuzzy Finder
winget install -e --id ajeetdsouza.zoxide   # Besseres 'cd' (z)`

*Hinweis: Falls Antigravity ganz neu ist, kann der Befehl `winget install Google.Antigravity` nötig sein (ohne ID-Präfix), aber die ID oben ist der Standard.*[winstall+1](https://winstall.app/apps/Google.Antigravity)

---

## Phase 2: Runtime-Setup (Node & Python)

Nach Phase 1 musst du dein **Terminal neu starten**, damit `fnm` und `uv` verfügbar sind.

**Für den MERN-Stack (Node.js):**

Statt eine feste Version zu installieren, nutzen wir `fnm`. Das macht Updates painless.

`powershell# Initialisiere fnm (nur einmal nötig, danach in dein $PROFILE eintragen)
fnm install --lts
fnm use lts

# Deine globalen MERN-Tools (State-of-the-Art 2026)
# nodemon braucht man kaum noch (node --watch), aber für Legacy gut.
# pnpm oder yarn sind oft beliebter als npm.
npm install -g yarn pnpm typescript ts-node eslint prettier @antfu/ni`

`*@antfu/ni` ist ein Geheimtipp: Es erlaubt dir `ni` statt `npm install`, `nr` statt `npm run` zu tippen – egal ob du npm, yarn oder pnpm im Projekt nutzt.*

**Für Python:**

Wir nutzen `uv`, das moderne Tool von Astral. Es ist rasend schnell. Powershell:

`# Python installieren (managed by uv, isoliert und sauber)
uv python install

# Globale Python Tools (installiert als isolierte Binaries)
uv tool install ruff      # Der Linter/Formatter Standard (ersetzt flake8/black)
uv tool install ipython   # Bessere REPL
uv tool install poetry    # Falls du Poetry für Dependency Management brauchst`

---

## Phase 3: Quality-of-Life aktivieren (Powershell Profile)

Damit `Antigravity`, `zoxide` (intelligentes cd) und `Starship` (schöner Prompt) immer laufen, musst du sie in dein Profil eintragen.

1. Tippe `notepad $PROFILE` in die PowerShell.
2. Füge das hier ein:

`powershell# FNM (Node Manager)
fnm env --use-on-cd | Out-String | Invoke-Expression

# Starship (Prompt)
Invoke-Expression (&starship init powershell)

# Zoxide (Smarter CD - benutze 'z ordner' statt 'cd ordner')
Invoke-Expression (& {
    $hook = if ($PSVersionTable.PSVersion.Major -lt 6) { 'startup' } else { 'pwd' }
    (zoxide init powershell --hook $hook) -join "`n"
})

# Aliases für die neuen Tools
Set-Alias cat bat
Set-Alias ls lsd
Set-Alias grep rg`

1. Speichern und PowerShell neu starten.

Jetzt hast du ein System, das schneller ist als 99% der Setups da draußen, mit der **Antigravity IDE** als Herzstück.[winget.ragerworks+1](https://winget.ragerworks.com/package/Google.Antigravity)

---

# 🔧 Troubleshooting (Update)

Hier sind Lösungen für Fehler, die typischerweise direkt nach einer frischen Installation auftreten können.

## 1. "Skripte können nicht geladen werden" (Execution Policy)

**Symptom:** Rote Fehlermeldung beim Start der PowerShell oder beim Ausführen von `npm install`, die `PSSecurityException` oder `UnauthorizedAccess` erwähnt.

**Lösung:** Windows blockiert standardmäßig Skripte. Wir müssen sie für den aktuellen Nutzer erlauben.

`powershellSet-ExecutionPolicy RemoteSigned -Scope CurrentUser
# Bestätige mit 'A' (Ja, alle)`

## 2. Node Version wird nicht gefunden ("lts" error)

**Symptom:** `fnm install --lts` bricht ab oder `fnm use` fragt endlos nach Installation.

**Ursache:** `fnm` hat noch keine aktuelle Liste der verfügbaren Node-Versionen vom Server geladen.

**Lösung:**

1. Liste aktualisieren: `fnm list-remote`
2. Explizite Version installieren (statt Alias): `fnm install 24.13.0` (oder aktuelle Version aus der Liste).

## 3. PowerShell Profil existiert nicht

**Symptom:** `notepad $PROFILE` sagt "Pfad nicht gefunden".

**Lösung:** Die Datei muss erst erstellt werden, bevor man sie bearbeiten kann.

`powershellif (!(Test-Path -Path $PROFILE)) { New-Item -ItemType File -Path $PROFILE -Force }
notepad $PROFILE`

## 4. Veraltete Zoxide Hooks

**Symptom:** Fehlermeldung im Terminal-Start: `invalid value 'startup' for '--hook'`.

**Lösung:** In neueren Versionen (ab 2025) wurde der `startup`-Hook entfernt.

Ändere in deinem `$PROFILE`:

- ❌ Alt: `zoxide init powershell --hook startup`
- ✅ Neu: `zoxide init powershell --hook pwd`

## 5. Alias Konflikte (cat, ls)

**Symptom:** Fehler `AllScope-Option kann nicht entfernt werden` für `cat` oder `ls`.

**Lösung:** Built-in Aliases von PowerShell lassen sich nicht einfach überschreiben. Statt `Set-Alias` müssen Funktionen definiert werden.

**Korrekter Code im $PROFILE:**

`powershellfunction cat { bat $args }
function ls { lsd $args }`

---

## 🧠 Philosophy: "Speed & Agents"

Dieses Setup ist darauf ausgelegt, die CLI-Interaktion zu minimieren und "Context Switching" zu verhindern.

1. **Native Speed:** Wir nutzen Rust-basierte Tools (`uv`, `fnm`, `ripgrep`), die millisekundenschnell starten.
2. **Agent First:** Code-Gerüste macht Antigravity; wir steuern die Architektur.
3. **Universal Commands:** Statt `npm`, `yarn` oder `pnpm` nutzen wir Universal-Wrapper.

        (aufklappen)

---

## ⚡ Quick Cheatsheet (Muscle Memory)

| **Aktion** | **Alt (Legacy)** | **Neu (Dein System)** | **Warum?** |
| --- | --- | --- | --- |
| Ordner wechseln | `cd projekt/backend` | **`z back`** | Springt intelligent zum häufigsten Ordner |
| Datei lesen | `cat file.js` | **`bat file.js`** | Syntax Highlighting & Git Integration |
| Dateien listen | `ls -la` | **`lsd -la`** | Icons, Farben, Tree-View möglich |
| Text suchen | `grep "error" .` | **`rg "error"`** | 10x schneller, ignoriert node_modules auto. |
| Node install | `npm i` | **`ni`** | Erkennt automatisch ob npm/pnpm/yarn |
| Script run | `npm run dev` | **`nr dev`** | Interaktive Auswahl wenn kein Script Name |
| Python venv | `python -m venv...` | **`uv venv`** | Erstellt Venv in Millisekunden |

---

## 🛠 Component Deep Dive

## 1. 🌌 Google Antigravity (IDE)

Deine Hauptzentrale. Anders als VS Code ist dies eine "Agentic IDE".

- **Key Feature:** Der "Context Awareness Loop". Antigravity kennt nicht nur die offene Datei, sondern deine gesamte Projektstruktur und Git-Historie.
- **Workflow:** Nutze `Cmd+K` (oder den jeweiligen Hotkey 2026), um Code nicht selbst zu schreiben, sondern zu *beschreiben*.
- **Integration:** Da wir Python/Node global via `fnm`/`uv` managen, muss in den Antigravity Settings oft nur der Pfad zum globalen Interpreter angegeben werden, falls er ihn nicht automatisch findet.

## 2. 🐢 Node.js & MERN Stack (via `fnm`)

Wir installieren Node niemals direkt, sondern nutzen den **Fast Node Manager**.

- **Version wechseln:**
    
    `powershellfnm install 24
    fnm use 24
    fnm default 24 # Macht es permanent`
    
- **Das `@antfu/ni` Geheimnis:**
    
    Du hast das Paket `ni` global installiert. Es schaut in dein Projektverzeichnis auf die `lock`-Datei und führt den richtigen Befehl aus.
    
    - `ni` -> installiert dependencies (egal ob yarn.lock, pnpm-lock.yaml oder package-lock.json existiert).
    - `nr` -> Startet scripts (npm run).
    - `nu` -> Updatet dependencies.
    - `nun` -> Uninstall dependencies.

## 3. 🐍 Python (via `uv`)

`uv` ersetzt pip, poetry und venv. Es ist der neue Standard 2026.

- **Projekt starten:**
    
    `powershelluv init my-project
    cd my-project
    uv run main.py # Erstellt venv on the fly und führt aus`
    
- **Dependency hinzufügen:**
    
    `powershelluv add requests fastapi`
    
    *Es ist nicht nötig, manuell virtuelle Umgebungen zu aktivieren. `uv run` regelt das.*
    

## 4. 💻 Terminal "Quality of Life"

## **Zoxide (`z`)**

Das ist dein Teleporter. Es lernt, welche Ordner du oft besuchst.

- Du warst einmal in `C:\Users\Dev\Projekte\Kunden\Meier\Backend`?
- Tippe einfach: `z meier` -> **BAM**, du bist da.

## **Ripgrep (`rg`)**

Wenn du etwas in deinem Code suchst:

- `rg "function login"` -> Findet sofort alle Stellen.
- Best Practice: Es respektiert `.gitignore`. Es sucht also nicht im `node_modules` oder `.git` Ordner (im Gegensatz zum normalen Windows Suchlauf).

## **FZF (Fuzzy Finder)**

(Meistens `Ctrl+R` in der PowerShell)

- Drücke `Ctrl+R` und tippe Teile eines Befehls, den du letzte Woche benutzt hast. Es sucht unscharf durch deine History.

---

## 🛡️ Maintenance & Updates

Um dein System frisch zu halten ("State-of-the-Art"), führe einmal im Monat folgendes aus:

`powershell# 1. Windows Software & Tools updaten
winget upgrade --all

# 2. Python Tools updaten
uv tool upgrade --all

# 3. Node Global Tools updaten
npm update -g @antfu/ni typescript`

---

## 📝 Troubleshooting

**Script Execution Policy Error?**

Falls PowerShell meckert, dass Scripte nicht ausgeführt werden dürfen:

`powershellSet-ExecutionPolicy RemoteSigned -Scope CurrentUser`

**Icons fehlen im Terminal?**

Stelle sicher, dass du in den Windows Terminal Einstellungen eine "Nerd Font" (z.B. *CaskaydiaCove Nerd Font* oder *MesloLGS NF*) ausgewählt hast. Ohne die siehst du bei `lsd` und Starship nur Kästchen.