"""Scheda Acqua (ATS): estrazione, tabella, statistiche, grafici ed export PDF.

Logica di parsing ed export invariata rispetto all'originale AcquaChiara.py,
riorganizzata come QWidget da inserire in una tab e con le utility condivise
spostate in bollettachiara.common.
"""
import re
from datetime import datetime

from PyQt6.QtWidgets import (QWidget, QPushButton, QFileDialog, QVBoxLayout,
                              QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
                              QHBoxLayout, QFrame, QMessageBox)
from PyQt6.QtGui import QFont

from .common import converti_numero, estrai_testo, MplCanvas, esporta_pdf_riepilogo


class AcquaTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dati_acqua = []

        main_layout = QVBoxLayout(self)

        btn_layout = QHBoxLayout()

        btn_load = QPushButton("📂 Carica PDF ATS")
        btn_load.setStyleSheet("background-color: #3498DB; color: white; font-weight: bold; padding: 12px; font-size: 14px; border-radius: 6px;")
        btn_load.clicked.connect(self.carica_pdf)
        btn_layout.addWidget(btn_load)

        btn_print = QPushButton("📄 Salva Riepilogo PDF")
        btn_print.setStyleSheet("background-color: #9B59B6; color: white; font-weight: bold; padding: 12px; font-size: 14px; border-radius: 6px;")
        btn_print.clicked.connect(self.esporta_riepilogo_pdf)
        btn_layout.addWidget(btn_print)

        btn_reset = QPushButton("🗑️ Reset")
        btn_reset.setStyleSheet("background-color: #E74C3C; color: white; font-weight: bold; padding: 12px; font-size: 14px; border-radius: 6px;")
        btn_reset.clicked.connect(self.reset_tutto)
        btn_layout.addWidget(btn_reset)

        main_layout.addLayout(btn_layout)

        content_layout = QHBoxLayout()

        self.table = QTableWidget()
        cols = ["Periodo", "Giorni", "Importo", "Consumo (mc)", "Costo/Giorno", "Media (mc/gg)", "File"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("QTableWidget { font-size: 13px; gridline-color: #ccc; } QHeaderView::section { background-color: #D6EAF8; padding: 5px; border: 1px solid #aaa; }")
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
        l = QVBoxLayout(box)
        t = QLabel(titolo.upper())
        t.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: bold;")
        widget.setStyleSheet(f"color: {colore}; font-size: 22px; font-weight: bold;")
        l.addWidget(t)
        l.addWidget(widget)
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

        for path in files:
            dati = self.analizza_ats(path)
            if dati:
                self.dati_acqua.append(dati)

        self.dati_acqua.sort(key=lambda x: x['data_fine'])
        self.aggiorna_interfaccia()

    def esporta_riepilogo_pdf(self):
        if not self.dati_acqua:
            QMessageBox.warning(self, "Attenzione", "Nessun dato da esportare.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Salva Riepilogo ATS", "Riepilogo_Acqua_ATS.pdf", "PDF Files (*.pdf)")

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
            QMessageBox.critical(self, "Errore ReportLab", f"Errore:\n{str(e)}\n\nAssicurati di aver installato reportlab.")

    def analizza_ats(self, path):
        text = estrai_testo(path, max_pagine=3)
        if not text:
            return None

        periodo_regex = re.search(r"Periodo\s+di\s+fatturazione\s*:\s*dal\s*(\d{2}/\d{2}/\d{4})\s*al\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
        if not periodo_regex:
            return None

        d_inizio = datetime.strptime(periodo_regex.group(1), "%d/%m/%Y").date()
        d_fine = datetime.strptime(periodo_regex.group(2), "%d/%m/%Y").date()
        giorni = (d_fine - d_inizio).days + 1
        periodo_str = f"{d_inizio.strftime('%b')} - {d_fine.strftime('%b %Y')}"

        importo_regex = re.search(r"(?:Totale\s+da\s+pagare|Totale\s+bolletta).*?(\d+[.,]\d+)\s*Euro", text, re.IGNORECASE | re.DOTALL)
        importo = converti_numero(importo_regex.group(1)) if importo_regex else 0.0

        consumo_regex = re.search(r"Totale\s+Consumi\s+fatturati\s*[:\.]?\s*(\d+(?:[.,]\d+)?)", text, re.IGNORECASE)
        consumo = converti_numero(consumo_regex.group(1)) if consumo_regex else 0.0

        return {
            "periodo": periodo_str,
            "data_fine": d_fine,
            "giorni": giorni,
            "importo": importo,
            "mc": consumo,
            "costo_die": importo / giorni if giorni > 0 else 0,
            "mc_die": consumo / giorni if giorni > 0 else 0,
            "file": path.split("/")[-1]
        }

    def aggiorna_interfaccia(self):
        tot_euro = 0
        tot_mc = 0
        tot_giorni = 0

        self.table.setRowCount(0)

        for d in self.dati_acqua:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(d['periodo']))
            self.table.setItem(row, 1, QTableWidgetItem(str(d['giorni'])))

            item_eur = QTableWidgetItem(f"€ {d['importo']:.2f}")
            item_eur.setFont(QFont("Arial", weight=QFont.Weight.Bold))
            self.table.setItem(row, 2, item_eur)

            self.table.setItem(row, 3, QTableWidgetItem(f"{d['mc']} mc"))
            self.table.setItem(row, 4, QTableWidgetItem(f"€ {d['costo_die']:.3f} /gg"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{d['mc_die']:.3f} mc/gg"))
            self.table.setItem(row, 6, QTableWidgetItem(d['file']))

            tot_euro += d['importo']
            tot_mc += d['mc']
            tot_giorni += d['giorni']

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

        labels = [d['periodo'] for d in self.dati_acqua]

        costi_die = [d['costo_die'] for d in self.dati_acqua]
        self.grafico_costi.axes.clear()
        bars = self.grafico_costi.axes.bar(labels, costi_die, color="#5DADE2")
        self.grafico_costi.axes.set_title("Costo Reale Giornaliero (€ al giorno)")
        self.grafico_costi.axes.grid(axis='y', linestyle='--', alpha=0.5)
        self.grafico_costi.axes.bar_label(bars, fmt='%.2f €', padding=3)
        self.grafico_costi.draw()

        consumi = [d['mc'] for d in self.dati_acqua]
        self.grafico_consumi.axes.clear()
        self.grafico_consumi.axes.plot(labels, consumi, marker='o', linestyle='-', color='#1ABC9C', linewidth=2)
        self.grafico_consumi.axes.fill_between(labels, consumi, color='#1ABC9C', alpha=0.1)
        self.grafico_consumi.axes.set_title("Volume Consumato (mc)")
        self.grafico_consumi.axes.grid(True, linestyle='--', alpha=0.5)
        for i, txt in enumerate(consumi):
            self.grafico_consumi.axes.annotate(f"{txt}", (labels[i], consumi[i]), textcoords="offset points", xytext=(0, 10), ha='center')
        self.grafico_consumi.draw()
