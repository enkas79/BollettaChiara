"""Entry point unificato di BollettaChiara: analizzatore bollette Luce/Gas/Acqua.

Sostituisce i precedenti script standalone BollettaChiara.py e AcquaChiara.py,
riunendo le due analisi in un'unica finestra a schede.
"""
import sys

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget

from bollettachiara.about import mostra_informazioni, mostra_guida
from bollettachiara.tab_energia import EnergiaTab
from bollettachiara.tab_acqua import AcquaTab


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

        azione_guida = menu_aiuto.addAction("Guida")
        azione_guida.triggered.connect(lambda: mostra_guida(self))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())
