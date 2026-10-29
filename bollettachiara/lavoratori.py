"""Worker su QThreadPool per eseguire il parsing PDF fuori dal main thread.

Il parsing con pdfplumber su PDF multipagina può bloccare la GUI: qui vive
in un QRunnable e comunica i risultati tramite segnali PyQt6.
"""
import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from . import parser
from .common import estrai_testo

log = logging.getLogger(__name__)


class SegnaliParsing(QObject):
    progresso = pyqtSignal(int, int, str)
    finito = pyqtSignal(list, list)
    errore = pyqtSignal(str)


class WorkerEnergia(QRunnable):
    """Analizza una lista di PDF bollette Luce/Gas in background."""

    def __init__(self, file_paths, segnali=None):
        super().__init__()
        self.file_paths = [Path(p) for p in file_paths]
        self.segnali = segnali or SegnaliParsing()

    def run(self):
        records = []
        saltati = []
        totale = len(self.file_paths)
        for i, path in enumerate(self.file_paths, start=1):
            self.segnali.progresso.emit(i, totale, path.name)
            try:
                testo = estrai_testo(str(path))
            except Exception as e:
                log.warning("PDF non leggibile %s: %s", path, e)
                saltati.append(f"{path.name} ({e})")
                continue
            if not testo:
                saltati.append(f"{path.name} (testo vuoto)")
                continue
            records.extend(parser.estrai_record_energia(testo, path.name))
        self.segnali.finito.emit(records, saltati)


class WorkerAcqua(QRunnable):
    """Analizza una lista di PDF bollette ATS in background."""

    def __init__(self, file_paths, segnali=None):
        super().__init__()
        self.file_paths = [Path(p) for p in file_paths]
        self.segnali = segnali or SegnaliParsing()

    def run(self):
        records = []
        saltati = []
        totale = len(self.file_paths)
        for i, path in enumerate(self.file_paths, start=1):
            self.segnali.progresso.emit(i, totale, path.name)
            try:
                testo = estrai_testo(str(path), max_pagine=3)
            except Exception as e:
                log.warning("PDF non leggibile %s: %s", path, e)
                saltati.append(f"{path.name} ({e})")
                continue
            rec = parser.analizza_ats_testo(testo, path.name)
            if rec is None:
                saltati.append(f"{path.name} (formato non riconosciuto)")
            else:
                records.append(rec)
        self.segnali.finito.emit(records, saltati)


def avvia_parsing(tipo, file_paths, segnali=None):
    """Avvia il worker sul QThreadPool globale. Ritorna i segnali usati."""
    if segnali is None:
        segnali = SegnaliParsing()
    cls = WorkerEnergia if tipo == "energia" else WorkerAcqua
    worker = cls(file_paths, segnali)
    QThreadPool.globalInstance().start(worker)
    return segnali
