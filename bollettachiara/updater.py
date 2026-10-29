"""Controllo aggiornamenti da GitHub Releases, fuori dal main thread.

Verifica l'ultima release via API GitHub, confronta con version.txt locale
e, se più recente, chiede conferma e scarica l'asset (in background).
Tutto il networking vive in QThread: il main thread riceve solo segnali.
"""
import json
import logging
import urllib.request
from pathlib import Path
from urllib.error import URLError

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from .versioni import confronta_versioni, leggi_versione_locale

log = logging.getLogger(__name__)

REPO = "enkas79/BollettaChiara"
API_ULTIMA_RELEASE = f"https://api.github.com/repos/{REPO}/releases/latest"
TIMEOUT = 15


class SegnaliUpdater(QObject):
    nessun_aggiornamento = pyqtSignal(str)
    nuova_versione = pyqtSignal(str, str, str)
    errore = pyqtSignal(str)
    download_finito = pyqtSignal(str)
    progresso_download = pyqtSignal(int, int)


class VerificaAggiornamentoThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.segnali = SegnaliUpdater()

    def run(self):
        locale = leggi_versione_locale()
        try:
            req = urllib.request.Request(API_ULTIMA_RELEASE, headers={"Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                dati = json.loads(resp.read().decode("utf-8"))
        except (URLError, OSError, json.JSONDecodeError) as e:
            log.warning("Controllo aggiornamenti fallito: %s", e)
            self.segnali.errore.emit(str(e))
            return

        remota = str(dati.get("tag_name", "")).lstrip("v")
        if confronta_versioni(remota, locale or ""):
            changelog = str(dati.get("body", ""))[:2000]
            url_download = self._scegli_asset(dati.get("assets", []))
            self.segnali.nuova_versione.emit(remota, changelog, url_download or "")
        else:
            self.segnali.nessun_aggiornamento.emit(locale or "?")

    @staticmethod
    def _scegli_asset(assets):
        """Preferisce .exe (Windows), poi .dmg, poi .deb."""
        for est in (".exe", ".dmg", ".deb"):
            for a in assets:
                nome = str(a.get("name", ""))
                if nome.lower().endswith(est):
                    return str(a.get("browser_download_url", ""))
        return ""


class DownloadAggiornamentoThread(QThread):
    def __init__(self, url, destinazione, parent=None):
        super().__init__(parent)
        self.url = url
        self.dest = Path(destinazione)
        self.segnali = SegnaliUpdater()
        self._annullato = False

    def run(self):
        try:
            req = urllib.request.Request(self.url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                totale = int(resp.headers.get("Content-Length") or 0)
                with open(self.dest, "wb") as f:
                    letto = 0
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        letto += len(chunk)
                        if totale:
                            self.segnali.progresso_download.emit(letto, totale)
            if not self._annullato:
                self.segnali.download_finito.emit(str(self.dest))
        except (URLError, OSError) as e:
            log.warning("Download aggiornamento fallito: %s", e)
            self.segnali.errore.emit(str(e))

    def annulla(self):
        self._annullato = True


def controlla_aggiornamenti(parent, automatico=False):
    """Avvia il controllo in background e collega i dialoghi al parent."""
    thread = VerificaAggiornamentoThread(parent)

    def _on_nuova(remota, changelog, url):
        testo = f"<p>È disponibile la versione <b>{remota}</b> (hai la {leggi_versione_locale()}).</p>"
        if changelog:
            testo += f"<p><b>Novità:</b><br>{changelog.replace(chr(10), '<br>')}</p>"
        if url:
            testo += "<p>Vuoi scaricare il nuovo installer?</p>"
            box = QMessageBox(parent)
            box.setWindowTitle("Aggiornamento disponibile")
            box.setTextFormat(box.TextFormat.RichText)
            box.setText(testo)
            btn_si = box.addButton("Scarica", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Più tardi", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is btn_si:
                _scarica(parent, url, remota)
        else:
            QMessageBox.information(parent, "Aggiornamento disponibile", testo)

    def _on_ok(locale):
        if not automatico:
            QMessageBox.information(parent, "Aggiornamenti", f"Stai usando l'ultima versione ({locale}).")

    def _on_errore(msg):
        if not automatico:
            QMessageBox.warning(parent, "Aggiornamenti", f"Impossibile controllare gli aggiornamenti:\n{msg}")

    thread.segnali.nuova_versione.connect(_on_nuova)
    thread.segnali.nessun_aggiornamento.connect(_on_ok)
    thread.segnali.errore.connect(_on_errore)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread


def _scarica(parent, url, versione):
    nome = url.rsplit("/", 1)[-1] or f"BollettaChiara-{versione}.bin"
    destinazione, _ = QFileDialog.getSaveFileName(parent, "Salva aggiornamento", nome)
    if not destinazione:
        return
    thread = DownloadAggiornamentoThread(url, destinazione, parent)

    def _on_fine(path):
        QMessageBox.information(parent, "Download completato",
                                f"Installer salvato in:\n{path}\n\nEseguilo per aggiornare.")

    thread.segnali.download_finito.connect(_on_fine)
    thread.segnali.errore.connect(lambda m: QMessageBox.warning(parent, "Download fallito", m))
    thread.finished.connect(thread.deleteLater)
    thread.start()
