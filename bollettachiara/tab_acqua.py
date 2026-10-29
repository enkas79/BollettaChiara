"""Scheda Acqua (ATS): tabella, statistiche, grafici ed export PDF.

Parsing in bollettachiara.parser, esecuzione su QThreadPool via
bollettachiara.lavoratori, presentazione qui.
"""
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
    QVBoxLayout,
    QWidget,
)

from .common import MplCanvas, esporta_pdf_riepilogo, stile_pulsante
from .lavoratori import avvia_parsing


class AcquaTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dati_acqua = []
        self._progresso = None
        self._segnali = None

        main_layout = QVBoxLayout(self)

        btn_layout = QHBoxLayout()

        self.btn_load = QPushButton("📂 Carica PDF ATS")
        self.btn_load.setStyleSheet(stile_pulsante("carica"))
        self.btn_load.clicked.connect(self.carica_pdf)
        btn_layout.addWidget(self.btn_load)

        self.btn_print = QPushButton("📄 Salva Riepilogo PDF")
        self.btn_print.setStyleSheet(stile_pulsante("esporta"))
        self.btn_print.clicked.connect(self.esporta_riepilogo_pdf)
        btn_layout.addWidget(self.btn_print)

        self.btn_reset = QPushButton("🗑️ Reset")
        self.btn_reset.setStyleSheet(stile_pulsante("reset"))
        self.btn_reset.clicked.connect(self.reset_tutto)
        btn_layout.addWidget(self.btn_reset)

        main_layout.addLayout(btn_layout)

        content_layout = QHBoxLayout()

        self.table = QTableWidget()
        cols = ["Periodo", "Giorni", "Importo", "Consumo (mc)", "Costo/Giorno", "Media (mc/gg)", "File"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { font-size: 13px; gridline-color: #ccc; }"
            " QHeaderView::section { background-color: #D6EAF8; padding: 5px; border: 1px solid #aaa; }"
        )
        content_layout.addWidget(self.table, stretch=2)

        stats_frame = QFrame()
        stats_frame.setFixedWidth(350)
        stats_frame.setStyleSheet("background-color: #ECF0F1; border-radius: 8px; border: 1px solid #BDC3C7;")
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(20, 20, 20, 20)

        stats_layout.addWidget(QLabel("<b>RIEPILOGO ACQUA</b>"))

        self.lbl_totale_euro = QLabel("€ 0.00")
        stats_layout.addWidget(self.crea_card("Totale Speso", self.lbl_totale_euro, "#2980B9"))

        self.lbl_totale_mc = QLabel("0 mc")
        stats_layout.addWidget(self.crea_card("Totale Metri Cubi", self.lbl_totale_mc, "#16A085"))

        self.lbl_costo_unitario = QLabel("€ 0.00 / mc")
        stats_layout.addWidget(self.crea_card("Costo Medio Unitario", self.lbl_costo_unitario, "#8E44AD"))

        self.lbl_stima_anno = QLabel("€ 0.00")
        stats_layout.addWidget(self.crea_card("Proiezione Annua", self.lbl_stima_anno, "#E67E22"))

        stats_layout.addStretch()
        content_layout.addWidget(stats_frame)

        main_layout.addLayout(content_layout)

        grafici_layout = QHBoxLayout()
        self.grafico_costi = MplCanvas(self, width=5, height=3)
        self.grafico_consumi = MplCanvas(self, width=5, height=3)
        grafici_layout.addWidget(self.grafico_costi)
        grafici_layout.addWidget(self.grafico_consumi)
        main_layout.addLayout(grafici_layout)

    def crea_card(self, titolo, widget, colore):
        box = QFrame()
        box.setStyleSheet("background-color: white; border-radius: 5px; border: 1px solid #ddd;")
        layout = QVBoxLayout(box)
        t = QLabel(titolo.upper())
        t.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: bold;")
        widget.setStyleSheet(f"color: {colore}; font-size: 22px; font-weight: bold;")
        layout.addWidget(t)
        layout.addWidget(widget)
        return box

    def reset_tutto(self):
        self.dati_acqua = []
        self.table.setRowCount(0)
        self.lbl_totale_euro.setText("€ 0.00")
        self.lbl_totale_mc.setText("0 mc")
        self.lbl_stima_anno.setText("€ 0.00")
        self.lbl_costo_unitario.setText("€ 0.00 / mc")
        self.grafico_costi.axes.clear()
        self.grafico_costi.draw()
        self.grafico_consumi.axes.clear()
        self.grafico_consumi.draw()

    def carica_pdf(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Seleziona Bollette ATS", "", "PDF Files (*.pdf)")
        if not files:
            return

        self.reset_tutto()
        self.btn_load.setEnabled(False)
        self.btn_print.setEnabled(False)
        self.btn_reset.setEnabled(False)

        self._progresso = QProgressDialog("Analisi bollette in corso...", "Annulla", 0, len(files), self)
        self._progresso.setWindowTitle("Caricamento")
        self._progresso.setMinimumDuration(300)

        self._segnali = avvia_parsing("acqua", files)
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

        self.dati_acqua = sorted(records, key=lambda x: x.data_fine)
        self.aggiorna_interfaccia()
        if saltati or any(r.avvisi for r in self.dati_acqua):
            messaggi = []
            if saltati:
                messaggi.append("File saltati:\n" + "\n".join(saltati))
            for r in self.dati_acqua:
                if r.avvisi:
                    messaggi.append(f"• {r.file}: " + "; ".join(r.avvisi))
            if messaggi:
                QMessageBox.warning(self, "Attenzione: dati parziali", "\n\n".join(messaggi))

    def esporta_riepilogo_pdf(self):
        if not self.dati_acqua:
            QMessageBox.warning(self, "Attenzione", "Nessun dato da esportare.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salva Riepilogo ATS", "Riepilogo_Acqua_ATS.pdf", "PDF Files (*.pdf)")

        if not file_path:
            return

        sezioni = [
            ("TOTALI E CONSUMI", [
                ("Numero Bollette", str(len(self.dati_acqua)), None),
                ("Totale Spesa", self.lbl_totale_euro.text(), "#2980B9"),
                ("Totale Metri Cubi", self.lbl_totale_mc.text(), "#16A085"),
            ]),
            ("INDICATORI E STIME", [
                ("Costo Medio Unitario", self.lbl_costo_unitario.text(), None),
                ("Proiezione Annua", self.lbl_stima_anno.text(), "#E67E22"),
            ]),
        ]

        try:
            esporta_pdf_riepilogo(file_path, "Report Analisi ACQUA", sezioni, colore_principale="#2980B9",
                                   footer_text="Documento generato da BollettaChiara")
            QMessageBox.information(self, "Successo", f"PDF salvato correttamente:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Errore ReportLab", f"Errore:\n{str(e)}")

    def aggiorna_interfaccia(self):
        tot_euro = 0
        tot_mc = 0
        tot_giorni = 0

        self.table.setRowCount(0)

        for d in self.dati_acqua:
            row = self.table.rowCount()
            self.table.insertRow(row)

            item_periodo = QTableWidgetItem(d.periodo)
            if d.avvisi:
                item_periodo.setForeground(QColor("#E67E22"))
                item_periodo.setToolTip("; ".join(d.avvisi))
            self.table.setItem(row, 0, item_periodo)

            self.table.setItem(row, 1, QTableWidgetItem(str(d.giorni)))

            item_eur = QTableWidgetItem(f"€ {d.importo:.2f}")
            item_eur.setFont(QFont("Arial", weight=QFont.Weight.Bold))
            self.table.setItem(row, 2, item_eur)

            self.table.setItem(row, 3, QTableWidgetItem(f"{d.mc} mc"))
            self.table.setItem(row, 4, QTableWidgetItem(f"€ {d.costo_die:.3f} /gg"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{d.mc_die:.3f} mc/gg"))
            self.table.setItem(row, 6, QTableWidgetItem(d.file))

            tot_euro += d.importo
            tot_mc += d.mc
            tot_giorni += d.giorni

        self.lbl_totale_euro.setText(f"€ {tot_euro:.2f}")
        self.lbl_totale_mc.setText(f"{tot_mc:.1f} mc")

        if tot_mc > 0:
            medio_unitario = tot_euro / tot_mc
            self.lbl_costo_unitario.setText(f"€ {medio_unitario:.3f} / mc")
        else:
            self.lbl_costo_unitario.setText("---")

        if tot_giorni > 0:
            media_giornaliera_euro = tot_euro / tot_giorni
            proiezione = media_giornaliera_euro * 365
            self.lbl_stima_anno.setText(f"€ {proiezione:.2f}")

        labels = [d.periodo for d in self.dati_acqua]

        costi_die = [d.costo_die for d in self.dati_acqua]
        self.grafico_costi.axes.clear()
        bars = self.grafico_costi.axes.bar(labels, costi_die, color="#5DADE2")
        self.grafico_costi.axes.set_title("Costo Reale Giornaliero (€ al giorno)")
        self.grafico_costi.axes.grid(axis='y', linestyle='--', alpha=0.5)
        self.grafico_costi.axes.bar_label(bars, fmt='%.2f €', padding=3)
        self.grafico_costi.draw()

        consumi = [d.mc for d in self.dati_acqua]
        self.grafico_consumi.axes.clear()
        self.grafico_consumi.axes.plot(labels, consumi, marker='o', linestyle='-', color='#1ABC9C', linewidth=2)
        self.grafico_consumi.axes.fill_between(labels, consumi, color='#1ABC9C', alpha=0.1)
        self.grafico_consumi.axes.set_title("Volume Consumato (mc)")
        self.grafico_consumi.axes.grid(True, linestyle='--', alpha=0.5)
        for i, txt in enumerate(consumi):
            self.grafico_consumi.axes.annotate(
                f"{txt}", (labels[i], consumi[i]), textcoords="offset points", xytext=(0, 10), ha='center')
        self.grafico_consumi.draw()
