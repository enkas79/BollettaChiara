"""Scheda Luce/Gas: tabella, statistiche, grafici ed export PDF.

La logica di parsing vive in bollettachiara.parser (modulo puro testabile);
qui si orchestrano worker su QThreadPool, presentazione e validazione.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import parser
from .common import MplCanvas, crea_box_statistica, esporta_pdf_riepilogo, stile_pulsante
from .lavoratori import avvia_parsing


class EnergiaTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dati_ordinati = []
        self.tipo_bolletta = "Bollette"
        self._progresso = None
        self._segnali = None

        main_layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()

        self.btn_load = QPushButton("📂 Carica Bollette")
        self.btn_load.setStyleSheet(stile_pulsante("carica"))
        self.btn_load.clicked.connect(self.carica_multipli_pdf)
        top_layout.addWidget(self.btn_load)

        self.btn_print = QPushButton("📄 Salva Riepilogo PDF")
        self.btn_print.setStyleSheet(stile_pulsante("esporta"))
        self.btn_print.clicked.connect(self.esporta_riepilogo_pdf)
        top_layout.addWidget(self.btn_print)

        self.btn_reset = QPushButton("🗑️ Reset")
        self.btn_reset.setStyleSheet(stile_pulsante("reset"))
        self.btn_reset.clicked.connect(self.reset_tutto)
        top_layout.addWidget(self.btn_reset)

        main_layout.addLayout(top_layout)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { height: 40px; width: 200px; font-size: 14px; font-weight: bold; color: #333; }
            QTabBar::tab:selected { border-bottom: 3px solid #2196F3; color: #000; background-color: #f0f0f0; }
            QTabWidget::pane { border: 1px solid #ccc; top: -1px; }
        """)
        main_layout.addWidget(self.tabs)

        self.tab_dati = QWidget()
        self.setup_tab_dati()
        self.tabs.addTab(self.tab_dati, "📋 Tabella Dati")

        self.tab_costi = QWidget()
        self.setup_tab_costi()
        self.tabs.addTab(self.tab_costi, "💰 Grafico Costi")

        self.tab_consumi = QWidget()
        self.setup_tab_consumi()
        self.tabs.addTab(self.tab_consumi, "⚡ Grafico Consumi")

    def setup_tab_dati(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget()
        colonne = ["Mese", "Totale Lordo", "Canone RAI", "Netto (Energia)", "Consumo", "Prezzo Unit.", "File Origine"]
        self.table.setColumnCount(len(colonne))
        self.table.setHorizontalHeaderLabels(colonne)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnHidden(2, True)
        self.table.setStyleSheet("""
            QTableWidget { font-size: 13px; alternate-background-color: #f9f9f9;
                           gridline-color: #ddd; border: 1px solid #ccc; }
            QHeaderView::section { background-color: #eee; padding: 8px;
                                   border: 1px solid #ccc; font-weight: bold; color: #333; }
            QTableWidget::item { padding: 5px; }
        """)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        layout.addWidget(self.table, stretch=1)

        stats_frame = QFrame()
        stats_frame.setFixedWidth(380)
        stats_frame.setStyleSheet("""
            QFrame { background-color: #F8F9FA; border-left: 1px solid #ddd; border-radius: 0px; }
        """)

        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setSpacing(15)
        stats_layout.setContentsMargins(20, 20, 20, 20)

        lbl_title = QLabel("RIEPILOGO ANALISI")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 900; color: #2C3E50; margin-bottom: 10px; border: none;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_layout.addWidget(lbl_title)

        lbl_sec1 = QLabel("TOTALI CUMULATIVI")
        lbl_sec1.setStyleSheet("font-size: 12px; font-weight: bold; color: #7F8C8D; letter-spacing: 1px; border: none;")
        stats_layout.addWidget(lbl_sec1)

        self.lbl_totale_soldi = QLabel("€ 0.00")
        stats_layout.addWidget(crea_box_statistica("Totale Netto", self.lbl_totale_soldi, "#27AE60"))

        self.lbl_totale_consumi = QLabel("0")
        stats_layout.addWidget(crea_box_statistica("Totale Consumi", self.lbl_totale_consumi, "#2C3E50"))

        self.lbl_totale_rai = QLabel("€ 0.00")
        stats_layout.addWidget(crea_box_statistica("Canone RAI", self.lbl_totale_rai, "#C0392B"))

        stats_layout.addSpacing(15)

        lbl_sec2 = QLabel("MEDIE E INDICI")
        lbl_sec2.setStyleSheet("font-size: 12px; font-weight: bold; color: #7F8C8D; letter-spacing: 1px; border: none;")
        stats_layout.addWidget(lbl_sec2)

        self.lbl_media_spesa = QLabel("€ 0.00")
        stats_layout.addWidget(crea_box_statistica("Spesa Media Mensile", self.lbl_media_spesa, "#333"))

        self.lbl_prezzo_medio = QLabel("---")
        stats_layout.addWidget(crea_box_statistica(
            "Prezzo Medio Unitario", self.lbl_prezzo_medio, "#2980B9", font_size="22px"))

        stats_layout.addStretch()
        layout.addWidget(stats_frame)
        self.tab_dati.setLayout(layout)

    def setup_tab_costi(self):
        layout = QVBoxLayout()
        self.canvas_costi = MplCanvas(self, width=5, height=4, dpi=100)
        layout.addWidget(self.canvas_costi)
        self.tab_costi.setLayout(layout)

    def setup_tab_consumi(self):
        layout = QVBoxLayout()
        self.canvas_consumi = MplCanvas(self, width=5, height=4, dpi=100)
        layout.addWidget(self.canvas_consumi)
        self.tab_consumi.setLayout(layout)

    def reset_tutto(self):
        self.dati_ordinati = []
        self.tipo_bolletta = "Bollette"
        self.table.setRowCount(0)
        self.table.setColumnHidden(2, True)

        self.canvas_costi.axes.clear()
        self.canvas_costi.draw()
        self.canvas_consumi.axes.clear()
        self.canvas_consumi.draw()

        self.lbl_totale_soldi.setText("€ 0.00")
        self.lbl_totale_consumi.setText("0")
        self.lbl_totale_rai.setText("€ 0.00")
        self.lbl_media_spesa.setText("€ 0.00")
        self.lbl_prezzo_medio.setText("---")

    def carica_multipli_pdf(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Seleziona Bollette", "", "PDF Files (*.pdf)")
        if not files:
            return
        self.reset_tutto()
        self.btn_load.setEnabled(False)
        self.btn_print.setEnabled(False)
        self.btn_reset.setEnabled(False)

        self._progresso = QProgressDialog("Analisi bollette in corso...", "Annulla", 0, len(files), self)
        self._progresso.setWindowTitle("Caricamento")
        self._progresso.setMinimumDuration(300)

        self._segnali = avvia_parsing("energia", files)
        self._segnali.progresso.connect(self._on_progresso)
        self._segnali.finito.connect(self._on_parsing_finito)

    def _on_progresso(self, attuale, totale, nome):
        if self._progresso is not None:
            self._progresso.setMaximum(totale)
            self._progresso.setValue(attuale)
            self._progresso.setLabelText(f"Analisi di: {nome} ({attuale}/{totale})")

    def _on_parsing_finito(self, records, saltati):
        if self._progresso is not None:
            self._progresso.reset()
            self._progresso = None
        self.btn_load.setEnabled(True)
        self.btn_print.setEnabled(True)
        self.btn_reset.setEnabled(True)

        records.sort(key=lambda r: (r.data_sort is None, r.data_sort or r.nome_file))
        self.dati_ordinati = records
        self.tipo_bolletta = parser.classifica_tipo(records)
        self._riempi_tabella(records)
        self._mostra_avvisi(records, saltati)

    def _riempi_tabella(self, records):
        self.table.setRowCount(0)
        trovato_rai = any(r.rai > 0 for r in records)
        unita_rilevata = ""
        conta_kwh = sum(1 for r in records if r.unita == "kwh")
        conta_smc = sum(1 for r in records if r.unita in ("smc", "mc"))
        if conta_kwh >= conta_smc and conta_kwh > 0:
            unita_rilevata = "kwh"
        elif conta_smc > 0:
            unita_rilevata = "smc"

        somma_netta = somma_consumi = somma_rai = 0.0

        for rec in records:
            row = self.table.rowCount()
            self.table.insertRow(row)

            display = rec.display if rec.data_sort is not None else f"⚠ {rec.display}"
            item_mese = QTableWidgetItem(display)
            if rec.incerto:
                item_mese.setForeground(QColor("#E67E22"))
                item_mese.setToolTip("; ".join(rec.avvisi) if rec.avvisi else "Dati parziali")
            self.table.setItem(row, 0, item_mese)

            self.table.setItem(row, 1, QTableWidgetItem(f"€ {rec.lordo:.2f}"))

            item_rai = QTableWidgetItem(f"€ {rec.rai:.2f}")
            if rec.rai > 0:
                item_rai.setForeground(QColor("#C0392B"))
            self.table.setItem(row, 2, item_rai)

            item_netto = QTableWidgetItem(f"€ {rec.netto:.2f}")
            item_netto.setFont(QFont("Arial", weight=QFont.Weight.Bold))
            self.table.setItem(row, 3, item_netto)

            consumo_str = f"{rec.consumo} {rec.unita}" if rec.consumo > 0 else "---"
            item_cons = QTableWidgetItem(consumo_str)
            if rec.consumo <= 0:
                item_cons.setForeground(QColor("#E67E22"))
            self.table.setItem(row, 4, item_cons)

            p_unit = rec.netto / rec.consumo if rec.consumo > 0 else 0
            item_prz = QTableWidgetItem(f"€ {p_unit:.3f}")
            item_prz.setForeground(QColor("#2980B9"))
            self.table.setItem(row, 5, item_prz)

            self.table.setItem(row, 6, QTableWidgetItem(rec.nome_file))

            somma_netta += rec.netto
            somma_consumi += rec.consumo
            somma_rai += rec.rai

        if trovato_rai:
            self.table.setColumnHidden(2, False)

        self.lbl_totale_soldi.setText(f"€ {somma_netta:.2f}")
        self.lbl_totale_consumi.setText(f"{somma_consumi:.1f} {unita_rilevata}")
        self.lbl_totale_rai.setText(f"€ {somma_rai:.2f}")

        avg_cost = somma_netta / len(records) if records else 0
        self.lbl_media_spesa.setText(f"€ {avg_cost:.2f}")

        if somma_consumi > 0:
            glob_avg = somma_netta / somma_consumi
            self.lbl_prezzo_medio.setText(f"€ {glob_avg:.3f} / {unita_rilevata}")

        self.aggiorna_grafici(records, unita_rilevata)

    def _mostra_avvisi(self, records, saltati):
        messaggi = []
        if saltati:
            messaggi.append("File saltati (non leggibili o formato non riconosciuto):\n" + "\n".join(saltati))
        incerti = [r for r in records if r.incerto]
        if incerti:
            righe = [f"• {r.nome_file} — {r.display}: " + ("; ".join(r.avvisi) if r.avvisi else "dati parziali")
                     for r in incerti]
            messaggi.append("Bollette con dati parziali (⚠ in tabella):\n" + "\n".join(righe))
        if messaggi:
            QMessageBox.warning(self, "Attenzione: dati parziali", "\n\n".join(messaggi))

    def esporta_riepilogo_pdf(self):
        if not self.dati_ordinati:
            QMessageBox.warning(self, "Attenzione", "Nessun dato da esportare.\nCarica prima le bollette.")
            return

        nome_suggerito = f"Riepilogo_{self.tipo_bolletta}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self, "Salva Riepilogo", nome_suggerito, "PDF Files (*.pdf)")

        if not file_path:
            return

        sezioni = [
            ("DATI E TOTALI", [
                ("Numero Bollette", str(len(self.dati_ordinati)), None),
                ("Totale Spesa (Netto)", self.lbl_totale_soldi.text(), "#27AE60"),
                ("Totale Consumi", self.lbl_totale_consumi.text(), None),
                ("Totale Canone RAI", self.lbl_totale_rai.text(), "#C0392B"),
            ]),
            ("INDICATORI DI PERFORMANCE", [
                ("Spesa Media Mensile", self.lbl_media_spesa.text(), None),
                ("Prezzo Medio Unitario", self.lbl_prezzo_medio.text(), "#2980B9"),
            ]),
        ]

        try:
            esporta_pdf_riepilogo(file_path, f"Report Analisi {self.tipo_bolletta}", sezioni,
                                   colore_principale="#2E86C1")
            QMessageBox.information(self, "Successo", f"PDF salvato correttamente:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Errore ReportLab", f"Errore durante la creazione del PDF:\n{str(e)}")

    def aggiorna_grafici(self, dati, unita):
        if not dati:
            return

        labels = [d.display for d in dati]
        valori_soldi = [d.netto for d in dati]
        valori_consumi = [d.consumo for d in dati]

        ax_costi = self.canvas_costi.axes
        ax_costi.clear()
        bars = ax_costi.bar(labels, valori_soldi, color='#2ECC71', alpha=0.8)
        ax_costi.set_title('Andamento Costi Netti (€)', fontsize=14, fontweight='bold', color='#333')
        ax_costi.grid(True, axis='y', linestyle='--', alpha=0.5)
        ax_costi.tick_params(axis='x', rotation=30, labelsize=10)
        ax_costi.bar_label(bars, fmt='€ %.0f', padding=3)
        self.canvas_costi.draw()

        ax_cons = self.canvas_consumi.axes
        ax_cons.clear()
        titolo = f'Andamento Consumi ({unita})' if unita else 'Andamento Consumi'
        ax_cons.plot(labels, valori_consumi, marker='o', linestyle='-', color='#3498DB', linewidth=3)
        ax_cons.fill_between(labels, valori_consumi, color='#3498DB', alpha=0.1)
        ax_cons.set_title(titolo, fontsize=14, fontweight='bold', color='#333')
        ax_cons.grid(True, linestyle='--', alpha=0.5)
        ax_cons.tick_params(axis='x', rotation=30, labelsize=10)
        for i, txt in enumerate(valori_consumi):
            ax_cons.annotate(f"{txt}", (labels[i], valori_consumi[i]), textcoords="offset points",
                             xytext=(0, 10), ha='center', fontweight='bold', color='#2C3E50')
        self.canvas_consumi.draw()
