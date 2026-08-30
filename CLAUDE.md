# Guidelines per Claude Code — BollettaChiara

## 1. Stack e Contesto Principale
* **Linguaggio Principale:** Python 3.11+ (Focus assoluto).
* **Framework GUI:** Esclusivamente **PyQt6** o **PySide6** (non usare Tkinter, CustomTkinter o altri framework).
* **Controllo Versione & CI/CD:** GitHub Actions (Build ed esecutabili multi-piattaforma generati da PyInstaller / NSIS, vedi `.github/workflows/build-installers.yml`).
* **Linguaggi Secondari (uso RARO):** PHP, JavaScript, Java. Usali solo se esplicitamente richiesto per integrazioni esterne.

## 2. Stato Attuale del Progetto
* Il repo contiene oggi due script PyQt6 standalone: `BollettaChiara.py` (bollette Luce/Gas) e `AcquaChiara.py` (bollette Acqua ATS). Sono strutturalmente duplicati (stesso pattern estrazione PDF, stessa UI, stesso export ReportLab).
* **Obiettivo di unificazione:** confluire entrambi in un'unica app (`main.py`) con tab per tipo di utenza (Luce/Gas/Acqua, eventualmente Rifiuti) e un motore di estrazione a parser pluggabili (uno per fornitore/tipo bolletta), condividendo canvas grafici, export PDF e tabella statistiche.
* Finché l'unificazione non è completata, `python BollettaChiara.py` e `python AcquaChiara.py` restano i due entry point eseguibili.
* Il sistema di autoupdate (sezione 4) e il modulo `updater` non sono ancora implementati: da introdurre insieme all'unificazione in `main.py`.

## 3. Componenti Obbligatori dell'Interfaccia (GUI)
* **Barra dei Menu (`QMenuBar`):** Ogni finestra principale dell'applicazione deve includere una barra dei menu strutturata con:
  * **Menu "Aiuto" / "Info":**
    * **Informazioni / About:** Finestra di dialogo (`QMessageBox.about`) contenente l'autore dell'applicazione e la versione corrente letta dinamicamente dal file `version.txt`.
    * **Controlla Aggiornamenti:** Voce di menu per avviare manualmente la verifica e il download di nuove versioni disponibili.
    * **Guida:** Voce che apre una finestra dedicata o un dialogo informativo con la guida all'uso dell'applicazione.
  * Altre voci di menu verranno specificate di volta in volta secondo le necessità del progetto.
* Le finestre attuali (`BollettaChiara.py`, `AcquaChiara.py`) non hanno ancora una `QMenuBar`: da aggiungere quando si interviene su di esse.

## 4. Gestione Versioni, Release & Autoupdate
* **File di Versione:** Il file `version.txt` situato nella root del progetto contiene il numero di versione corrente (es. `1.0.0`).
* **Trigger di Build:** Ogni volta che si apportano modifiche, fix o nuove funzionalità ai file di codice, **aggiorna sempre il numero di versione in `version.txt`** (incrementando la versione patch o minor). Questo scatenerà automaticamente la build degli installer tramite il workflow `.github/workflows/build-installers.yml`.
* Il workflow di build richiede `main.py`, `pyproject.toml` (extra `[gui]`) e uno scheletro `packaging/` (NSIS per Windows, control file per il `.deb`) non ancora presenti: da creare quando si procede con l'unificazione dei due script.
* **Sistema di Autoupdate:**
  * **Verifica Automatica all'Avvio:** L'applicazione deve verificare in background (tramite API GitHub Releases o endpoint dedicato) la presenza di nuove versioni confrontando la versione remota con quella locale in `version.txt`.
  * **Notifica e Download:** Se è disponibile una nuova release, mostrare un dialogo informativo (`QMessageBox` o dialogo custom con changelog) chiedendo all'utente se desidera aggiornare.
  * **Installazione / Sostituzione:** Gestire il download dell'installer/binario aggiornato ed eseguire il processo di aggiornamento/riavvio senza bloccare l'esperienza utente.

## 5. Standard di Sviluppo GUI (Qt & Python)
* **Threading/Asincronia:** NON eseguire mai operazioni I/O, download, chiamate API di rete, controllo aggiornamenti o computazioni pesanti (parsing PDF su liste lunghe) nel thread principale dell'interfaccia. Usa sempre `QThread` (o `QThreadPool`/`QRunnable`) e i segnali (`pyqtSignal` / `Signal`) per aggiornare la GUI, notificare l'esito dei controlli di update o l'avanzamento dei download, ed evitare che l'applicazione si blocchi.
* **Separazione Architetturale:** Separa rigorosamente la logica dell'interfaccia grafica (layout, widget, segnali) dalla logica di business/backend (parsing PDF, calcolo statistiche, export) e dal modulo di aggiornamento (`updater`).
* **Gestione Errori:** Intercetta le eccezioni (incluse quelle di rete/I/O durante l'autoupdate) e mostra messaggi chiari all'utente tramite dialoghi Qt (`QMessageBox.critical` o `QMessageBox.warning`) anziché far crashare il programma nel terminale o fallire silenziosamente (es. `except: return 0.0`). Gli errori di autoupdate in background vanno gestiti silenziosamente, quelli su richiesta manuale mostrati con dialogo.

## 6. Comandi di Sviluppo & Test
* **Esecuzione App (stato attuale):** `python BollettaChiara.py` oppure `python AcquaChiara.py`
* **Esecuzione App (dopo unificazione):** `python main.py`
* **Test Suite:** `pytest`
* **Linter / Formatting:** `ruff check . --fix`
* **Dipendenze:** `pip freeze > requirements.txt`

## 7. Regole Operative per l'Agente
* **Lingua:** Rispondi e inserisci commenti nel codice sempre in **italiano**.
* **Stile Risposte:** Sii sintetico e diretto. Vai subito al codice e ai comandi, evitando preamboli teorici o spiegazioni prolisse.
* **Autonomia e Versionamento:** Ricordati di aggiornare `version.txt` a ogni modifica rilevante ai file di progetto per garantire che la release su GitHub venga generata correttamente.
* **Gestione Git e Branch:** Una volta creato il branch e completate le modifiche, procedi direttamente al push/merge nel branch principale (`main`/`master`) in piena autonomia, senza richiedere conferme.
* **Pulizia Repo:** Non creare file di spazzatura, note `.md` extra o backup nella repository a meno che non sia l'utente a chiederlo esplicitamente.
