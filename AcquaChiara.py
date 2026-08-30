import sys
import re
import pdfplumber
from datetime import date, datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, 
                             QTextEdit, QFileDialog, QVBoxLayout, QWidget, 
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QHBoxLayout, QFrame, QTabWidget, QMessageBox)
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtCore import Qt

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

# --- NUOVO SISTEMA DI STAMPA: REPORTLAB ---
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
except ImportError:
    print("ERRORE: Libreria 'reportlab' mancante. Esegui 'pip install reportlab' nel terminale.")

# --- GRAFICI ---
class CanvasGrafico(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111) 
        fig.tight_layout(pad=3.0)
        super(CanvasGrafico, self).__init__(fig)

# --- PROGRAMMA PRINCIPALE ---
class AnalizzatoreAcquaATS(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Analizzatore Acqua ATS - Alto Trevigiano Servizi")
        self.dati_acqua = []

        # Layout Principale
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 1. BOTTONI IN ALTO
        btn_layout = QHBoxLayout()
        
        # Tasto Carica
        btn_load = QPushButton("📂 Carica PDF ATS")
        btn_load.setStyleSheet("background-color: #3498DB; color: white; font-weight: bold; padding: 12px; font-size: 14px; border-radius: 6px;")
        btn_load.clicked.connect(self.carica_pdf)
        btn_layout.addWidget(btn_load)

        # Tasto Stampa (AGGIORNATO A REPORTLAB)
        btn_print = QPushButton("📄 Salva Riepilogo PDF")
        btn_print.setStyleSheet("background-color: #9B59B6; color: white; font-weight: bold; padding: 12px; font-size: 14px; border-radius: 6px;")
        btn_print.clicked.connect(self.esporta_riepilogo_reportlab)
        btn_layout.addWidget(btn_print)

        # Tasto Reset
        btn_reset = QPushButton("🗑️ Reset")
        btn_reset.setStyleSheet("background-color: #E74C3C; color: white; font-weight: bold; padding: 12px; font-size: 14px; border-radius: 6px;")
        btn_reset.clicked.connect(self.reset_tutto)
        btn_layout.addWidget(btn_reset)

        main_layout.addLayout(btn_layout)

        # 2. TABELLA E STATISTICHE
        content_layout = QHBoxLayout()

        # Tabella
        self.table = QTableWidget()
        cols = ["Periodo", "Giorni", "Importo", "Consumo (mc)", "Costo/Giorno", "Media (mc/gg)", "File"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("QTableWidget { font-size: 13px; gridline-color: #ccc; } QHeaderView::section { background-color: #D6EAF8; padding: 5px; border: 1px solid #aaa; }")
        content_layout.addWidget(self.table, stretch=2)

        # Box Statistiche Laterale
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

        # 3. GRAFICI
        grafici_layout = QHBoxLayout()
        self.grafico_costi = CanvasGrafico(self, width=5, height=3)
        self.grafico_consumi = CanvasGrafico(self, width=5, height=3)
        grafici_layout.addWidget(self.grafico_costi)
        grafici_layout.addWidget(self.grafico_consumi)
        main_layout.addLayout(grafici_layout)

        # 4. PULSANTE ESCI
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.btn_exit = QPushButton("❌ Esci")
        self.btn_exit.setFixedWidth(150)
        self.btn_exit.setStyleSheet("""
            QPushButton { background-color: #95A5A6; color: white; font-weight: bold; padding: 12px; border-radius: 5px; font-size: 16px; }
            QPushButton:hover { background-color: #7F8C8D; }
        """)
        self.btn_exit.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_exit)
        
        main_layout.addLayout(bottom_layout)

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
        if not files: return
        
        self.reset_tutto()
        
        for path in files:
            dati = self.analizza_ats(path)
            if dati:
                self.dati_acqua.append(dati)

        # Ordina per data
        self.dati_acqua.sort(key=lambda x: x['data_fine'])
        self.aggiorna_interfaccia()

    # --- NUOVO METODO EXPORT PDF (REPORTLAB + HEXCOLOR FIX) ---
    def esporta_riepilogo_reportlab(self):
        if not self.dati_acqua:
            QMessageBox.warning(self, "Attenzione", "Nessun dato da esportare.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Salva Riepilogo ATS", "Riepilogo_Acqua_ATS.pdf", "PDF Files (*.pdf)")
        
        if not file_path:
            return 

        try:
            # 1. Creazione Canvas
            c = canvas.Canvas(file_path, pagesize=A4)
            width, height = A4
            
            # --- HEADER ---
            c.setStrokeColor(colors.HexColor("#2980B9")) # Blu Acqua
            c.setLineWidth(2)
            c.line(50, height - 50, width - 50, height - 50)
            
            c.setFont("Helvetica-Bold", 24)
            c.setFillColor(colors.HexColor("#2980B9"))
            c.drawCentredString(width / 2, height - 90, "Report Analisi ACQUA")
            
            c.setFont("Helvetica", 10)
            c.setFillColor(colors.black)
            c.drawCentredString(width / 2, height - 110, f"Generato il: {date.today().strftime('%d/%m/%Y')}")

            # Funzione helper per le righe
            def disegna_riga(y, etichetta, valore, colore_valore=colors.black):
                c.setFillColor(colors.whitesmoke)
                c.rect(50, y - 5, width - 100, 30, fill=1, stroke=0)
                
                c.setFont("Helvetica-Bold", 12)
                c.setFillColor(colors.darkslategray)
                c.drawString(70, y + 5, etichetta)
                
                c.setFont("Helvetica-Bold", 14)
                c.setFillColor(colore_valore)
                c.drawRightString(width - 70, y + 5, str(valore))
                return y - 40 

            # --- SEZIONE 1: TOTALI ---
            y_pos = height - 160
            
            c.setFillColor(colors.HexColor("#2980B9"))
            c.rect(50, y_pos, width - 100, 25, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(60, y_pos + 7, "TOTALI E CONSUMI")
            y_pos -= 40

            y_pos = disegna_riga(y_pos, "Numero Bollette", str(len(self.dati_acqua)))
            y_pos = disegna_riga(y_pos, "Totale Spesa", self.lbl_totale_euro.text(), colors.HexColor("#2980B9"))
            y_pos = disegna_riga(y_pos, "Totale Metri Cubi", self.lbl_totale_mc.text(), colors.HexColor("#16A085"))
            
            y_pos -= 20

            # --- SEZIONE 2: INDICATORI ---
            c.setFillColor(colors.HexColor("#8E44AD")) # Viola
            c.rect(50, y_pos, width - 100, 25, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(60, y_pos + 7, "INDICATORI E STIME")
            y_pos -= 40

            y_pos = disegna_riga(y_pos, "Costo Medio Unitario", self.lbl_costo_unitario.text())
            y_pos = disegna_riga(y_pos, "Proiezione Annua", self.lbl_stima_anno.text(), colors.HexColor("#E67E22")) # Arancione

            # Footer
            c.setFont("Helvetica", 8)
            c.setFillColor(colors.gray)
            c.drawCentredString(width / 2, 50, "Documento generato da Analizzatore Acqua ATS")

            c.save()
            QMessageBox.information(self, "Successo", f"PDF salvato correttamente:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Errore ReportLab", f"Errore:\n{str(e)}\n\nAssicurati di aver installato reportlab.")

    def converti_numero(self, s):
        try: return float(s.replace('.','').replace(',','.'))
        except: return 0.0

    def analizza_ats(self, path):
        text = ""
        try:
            with pdfplumber.open(path) as pdf:
                for i, p in enumerate(pdf.pages):
                    if i > 2: break
                    text += p.extract_text() + "\n"
        except: return None

        # Pattern ATS
        periodo_regex = re.search(r"Periodo\s+di\s+fatturazione\s*:\s*dal\s*(\d{2}/\d{2}/\d{4})\s*al\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
        if not periodo_regex: return None 

        d_inizio = datetime.strptime(periodo_regex.group(1), "%d/%m/%Y").date()
        d_fine = datetime.strptime(periodo_regex.group(2), "%d/%m/%Y").date()
        giorni = (d_fine - d_inizio).days + 1
        periodo_str = f"{d_inizio.strftime('%b')} - {d_fine.strftime('%b %Y')}"

        importo_regex = re.search(r"(?:Totale\s+da\s+pagare|Totale\s+bolletta).*?(\d+[.,]\d+)\s*Euro", text, re.IGNORECASE | re.DOTALL)
        importo = self.converti_numero(importo_regex.group(1)) if importo_regex else 0.0

        consumo_regex = re.search(r"Totale\s+Consumi\s+fatturati\s*[:\.]?\s*(\d+(?:[.,]\d+)?)", text, re.IGNORECASE)
        consumo = self.converti_numero(consumo_regex.group(1)) if consumo_regex else 0.0

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

        # Aggiorna Statistiche
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
        
        # Aggiorna Grafici
        labels = [d['periodo'] for d in self.dati_acqua]
        
        # Grafico 1: Costo al giorno (Barre)
        costi_die = [d['costo_die'] for d in self.dati_acqua]
        self.grafico_costi.axes.clear()
        bars = self.grafico_costi.axes.bar(labels, costi_die, color="#5DADE2")
        self.grafico_costi.axes.set_title("Costo Reale Giornaliero (€ al giorno)")
        self.grafico_costi.axes.grid(axis='y', linestyle='--', alpha=0.5)
        self.grafico_costi.axes.bar_label(bars, fmt='%.2f €', padding=3)
        self.grafico_costi.draw()

        # Grafico 2: Consumo mc (Linea)
        consumi = [d['mc'] for d in self.dati_acqua]
        self.grafico_consumi.axes.clear()
        self.grafico_consumi.axes.plot(labels, consumi, marker='o', linestyle='-', color='#1ABC9C', linewidth=2)
        self.grafico_consumi.axes.fill_between(labels, consumi, color='#1ABC9C', alpha=0.1)
        self.grafico_consumi.axes.set_title("Volume Consumato (mc)")
        self.grafico_consumi.axes.grid(True, linestyle='--', alpha=0.5)
        for i, txt in enumerate(consumi):
             self.grafico_consumi.axes.annotate(f"{txt}", (labels[i], consumi[i]), textcoords="offset points", xytext=(0,10), ha='center')
        self.grafico_consumi.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnalizzatoreAcquaATS()
    window.showMaximized()
    sys.exit(app.exec())