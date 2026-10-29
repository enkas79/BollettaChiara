"""Entry point unificato di BollettaChiara: analizzatore bollette Luce/Gas/Acqua.

Sostituisce i precedenti script standalone BollettaChiara.py e AcquaChiara.py,
riunendo le due analisi in un'unica finestra a schede.
"""
import logging
import sys

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget

from bollettachiara.about import mostra_guida, mostra_informazioni
from bollettachiara.tab_acqua import AcquaTab
from bollettachiara.tab_energia import EnergiaTab
from bollettachiara.updater import controlla_aggiornamenti


def configura_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BollettaChiara")

        self._crea_menu()

        tabs = QTabWidget()
        tabs.addTab(EnergiaTab(), "💡 Luce / Gas")
        tabs.addTab(AcquaTab(), "💧 Acqua")
        self.setCentralWidget(tabs)

    def _crea_menu(self):
        menu_aiuto = self.menuBar().addMenu("&Aiuto")

        azione_info = menu_aiuto.addAction("Informazioni")
        azione_info.triggered.connect(lambda: mostra_informazioni(self))

        azione_aggiornamenti = menu_aiuto.addAction("Controlla aggiornamenti")
        azione_aggiornamenti.triggered.connect(lambda: controlla_aggiornamenti(self, automatico=False))

        azione_guida = menu_aiuto.addAction("Guida")
        azione_guida.triggered.connect(lambda: mostra_guida(self))


if __name__ == "__main__":
    configura_logging()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    controlla_aggiornamenti(window, automatico=True)
    sys.exit(app.exec())
