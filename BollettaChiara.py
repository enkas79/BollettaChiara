import sys
import re
import pdfplumber
from datetime import date

# Import PyQt6 necessari
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, 
                             QTextEdit, QFileDialog, QVBoxLayout, QWidget, 
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QHBoxLayout, QFrame, QTabWidget, QMessageBox, QSpacerItem, QSizePolicy)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt

# Import Matplotlib per i grafici
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

# --- CLASSE PER I GRAFICI ---
class SingleMplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111) 
        fig.tight_layout(pad=3.0)
        super(SingleMplCanvas, self).__init__(fig)

# --- CLASSE PRINCIPALE ---
class AnalizzatoreBollette(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Analizzatore Bollette PRO")
        self.dati_ordinati = []
        self.tipo_bolletta = "Bollette" # Variabile per memorizzare se è Luce o Gas

        # --- LAYOUT PRINCIPALE ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 1. BARRA SUPERIORE
        top_layout = QHBoxLayout()
        
        self.btn_load = QPushButton("📂 Carica Bollette")
        self.btn_load.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; border-radius: 5px; font-size: 14px; }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.btn_load.clicked.connect(self.carica_multipli_pdf)
        top_layout.addWidget(self.btn_load)

        # PULSANTE PER ESPORTARE IL RIEPILOGO PDF
        self.btn_print = QPushButton("📄 Salva Riepilogo PDF")
        self.btn_print.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 10px; border-radius: 5px; font-size: 14px; }
            QPushButton:hover { background-color: #1976D2; }
        """)
        self.btn_print.clicked.connect(self.esporta_riepilogo_reportlab)
        top_layout.addWidget(self.btn_print)

        self.btn_reset = QPushButton("🗑️ Reset")
        self.btn_reset.setStyleSheet("""
            QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 10px; border-radius: 5px; font-size: 14px; }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self.btn_reset.clicked.connect(self.reset_tutto)
        top_layout.addWidget(self.btn_reset)

        main_layout.addLayout(top_layout)

        # 2. SISTEMA A SCHEDE (TABS)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { height: 40px; width: 200px; font-size: 14px; font-weight: bold; color: #333; }
            QTabBar::tab:selected { border-bottom: 3px solid #2196F3; color: #000; background-color: #f0f0f0; }
            QTabWidget::pane { border: 1px solid #ccc; top: -1px; }
        """)
        main_layout.addWidget(self.tabs)

        # SCHEDA 1: TABELLA DATI
        self.tab_dati = QWidget()
        self.setup_tab_dati()
        self.tabs.addTab(self.tab_dati, "📋 Tabella Dati")

        # SCHEDA 2: GRAFICO COSTI
        self.tab_costi = QWidget()
        self.setup_tab_costi()
        self.tabs.addTab(self.tab_costi, "💰 Grafico Costi")

        # SCHEDA 3: GRAFICO CONSUMI
        self.tab_consumi = QWidget()
        self.setup_tab_consumi()
        self.tabs.addTab(self.tab_consumi, "⚡ Grafico Consumi")

        # 3. BARRA INFERIORE
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch() 
        
        self.btn_exit = QPushButton("❌ Esci")
        self.btn_exit.setFixedWidth(150)
        self.btn_exit.setStyleSheet("""
            QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 10px; border-radius: 5px; font-size: 14px; }
            QPushButton:hover { background-color: #d32f2f; }
        """)
        self.btn_exit.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_exit)
        
        main_layout.addLayout(bottom_layout)

    # --- SETUP TABELLA E SIDEBAR ---
    def setup_tab_dati(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # --- A. TABELLA (SINISTRA) ---
        self.table = QTableWidget()
        colonne = ["Mese", "Totale Lordo", "Canone RAI", "Netto (Energia)", "Consumo", "Prezzo Unit.", "File Origine"]
        self.table.setColumnCount(len(colonne))
        self.table.setHorizontalHeaderLabels(colonne)
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
        self.table.setColumnHidden(2, True) 
        self.table.setStyleSheet("""
            QTableWidget { font-size: 13px; alternate-background-color: #f9f9f9; gridline-color: #ddd; border: 1px solid #ccc; }
            QHeaderView::section { background-color: #eee; padding: 8px; border: 1px solid #ccc; font-weight: bold; color: #333; }
            QTableWidget::item { padding: 5px; }
        """)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        
        layout.addWidget(self.table, stretch=1)

        # --- B. SIDEBAR STATISTICHE (DESTRA) ---
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
        stats_layout.addWidget(self.crea_box_statistica("Totale Netto", self.lbl_totale_soldi, "#27AE60")) 

        self.lbl_totale_consumi = QLabel("0")
        stats_layout.addWidget(self.crea_box_statistica("Totale Consumi", self.lbl_totale_consumi, "#2C3E50")) 

        self.lbl_totale_rai = QLabel("€ 0.00")
        stats_layout.addWidget(self.crea_box_statistica("Canone RAI", self.lbl_totale_rai, "#C0392B")) 

        stats_layout.addSpacing(15)

        lbl_sec2 = QLabel("MEDIE E INDICI")
        lbl_sec2.setStyleSheet("font-size: 12px; font-weight: bold; color: #7F8C8D; letter-spacing: 1px; border: none;")
        stats_layout.addWidget(lbl_sec2)

        self.lbl_media_spesa = QLabel("€ 0.00")
        stats_layout.addWidget(self.crea_box_statistica("Spesa Media Mensile", self.lbl_media_spesa, "#333"))

        self.lbl_prezzo_medio = QLabel("---")
        stats_layout.addWidget(self.crea_box_statistica("Prezzo Medio Unitario", self.lbl_prezzo_medio, "#2980B9", font_size="22px"))

        stats_layout.addStretch()
        layout.addWidget(stats_frame)
        self.tab_dati.setLayout(layout)

    def crea_box_statistica(self, titolo, widget_valore, colore_testo, font_size="20px"):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame { 
                background-color: white; 
                border-radius: 10px; 
                border: 1px solid #E0E0E0; 
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(2)

        lbl_titolo = QLabel(titolo.upper())
        lbl_titolo.setStyleSheet("color: #7F8C8D; font-size: 11px; font-weight: bold; border: none;")
        layout.addWidget(lbl_titolo)

        widget_valore.setStyleSheet(f"color: {colore_testo}; font-size: {font_size}; font-weight: bold; border: none;")
        widget_valore.setWordWrap(True)
        layout.addWidget(widget_valore)

        return frame

    def setup_tab_costi(self):
        layout = QVBoxLayout()
        self.canvas_costi = SingleMplCanvas(self, width=5, height=4, dpi=100)
        layout.addWidget(self.canvas_costi)
        self.tab_costi.setLayout(layout)

    def setup_tab_consumi(self):
        layout = QVBoxLayout()
        self.canvas_consumi = SingleMplCanvas(self, width=5, height=4, dpi=100)
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
        print("Reset effettuato.")

    def carica_multipli_pdf(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Seleziona Bollette", "", "PDF Files (*.pdf)")
        if files:
            self.analizza_lista_files(files)

    # --- NUOVO METODO ESPORTA RIEPILOGO CON REPORTLAB (CORRETTO HEXCOLOR) ---
    def esporta_riepilogo_reportlab(self):
        if not self.dati_ordinati:
            QMessageBox.warning(self, "Attenzione", "Nessun dato da esportare.\nCarica prima le bollette.")
            return

        # Nome file suggerito
        nome_suggerito = f"Riepilogo_{self.tipo_bolletta}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self, "Salva Riepilogo", nome_suggerito, "PDF Files (*.pdf)")
        
        if not file_path:
            return 

        try:
            # 1. Creazione Canvas (Foglio A4)
            c = canvas.Canvas(file_path, pagesize=A4)
            width, height = A4
            
            # --- HEADER ---
            # CORREZIONE: Uso colors.HexColor invece di colors.hexval
            c.setStrokeColor(colors.HexColor("#2E86C1")) 
            c.setLineWidth(2)
            c.line(50, height - 50, width - 50, height - 50) 
            
            c.setFont("Helvetica-Bold", 24)
            c.setFillColor(colors.HexColor("#2E86C1"))
            c.drawCentredString(width / 2, height - 90, f"Report Analisi {self.tipo_bolletta}")
            
            c.setFont("Helvetica", 10)
            c.setFillColor(colors.black)
            c.drawCentredString(width / 2, height - 110, f"Generato il: {date.today().strftime('%d/%m/%Y')}")

            # Funzione helper per disegnare righe della tabella
            def disegna_riga(y, etichetta, valore, colore_valore=colors.black):
                # Sfondo riga
                c.setFillColor(colors.whitesmoke)
                c.rect(50, y - 5, width - 100, 30, fill=1, stroke=0)
                
                # Etichetta
                c.setFont("Helvetica-Bold", 12)
                c.setFillColor(colors.darkslategray)
                c.drawString(70, y + 5, etichetta)
                
                # Valore
                c.setFont("Helvetica-Bold", 14)
                c.setFillColor(colore_valore)
                c.drawRightString(width - 70, y + 5, str(valore))
                
                return y - 40 # Ritorna la nuova posizione Y

            # --- SEZIONE 1: TOTALI ---
            y_pos = height - 160
            
            # Titolo Sezione
            c.setFillColor(colors.HexColor("#2E86C1"))
            c.rect(50, y_pos, width - 100, 25, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(60, y_pos + 7, "DATI E TOTALI")
            y_pos -= 40

            # Righe Dati
            y_pos = disegna_riga(y_pos, "Numero Bollette", str(len(self.dati_ordinati)))
            y_pos = disegna_riga(y_pos, "Totale Spesa (Netto)", self.lbl_totale_soldi.text(), colors.HexColor("#27AE60")) # Verde
            y_pos = disegna_riga(y_pos, "Totale Consumi", self.lbl_totale_consumi.text())
            y_pos = disegna_riga(y_pos, "Totale Canone RAI", self.lbl_totale_rai.text(), colors.HexColor("#C0392B")) # Rosso
            
            y_pos -= 20 # Spazio extra

            # --- SEZIONE 2: INDICATORI ---
            # Titolo Sezione
            c.setFillColor(colors.HexColor("#2E86C1"))
            c.rect(50, y_pos, width - 100, 25, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(60, y_pos + 7, "INDICATORI DI PERFORMANCE")
            y_pos -= 40

            # Righe Dati
            y_pos = disegna_riga(y_pos, "Spesa Media Mensile", self.lbl_media_spesa.text())
            y_pos = disegna_riga(y_pos, "Prezzo Medio Unitario", self.lbl_prezzo_medio.text(), colors.HexColor("#2980B9")) # Blu

            # Footer
            c.setFont("Helvetica", 8)
            c.setFillColor(colors.gray)
            c.drawCentredString(width / 2, 50, "Documento generato da Analizzatore Bollette PRO")

            c.save()
            QMessageBox.information(self, "Successo", f"PDF salvato correttamente:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Errore ReportLab", f"Errore durante la creazione del PDF:\n{str(e)}\n\nHai installato la libreria? (pip install reportlab)")

    def analizza_lista_files(self, file_paths):
        self.reset_tutto()
        temp_list = []
        trovato_rai = False
        unita_rilevata = ""
        conta_kwh = 0
        conta_smc = 0

        print(f"Inizio analisi di {len(file_paths)} file...")

        for path in file_paths:
            nome_file = path.split("/")[-1]
            testo = self.estrai_testo(path)
            
            dati = self.estrai_dati_completi(testo)
            data_obj, display = self.estrai_data_competenza(testo)
            
            if dati['rai'] > 0: trovato_rai = True
            
            # Logica per determinare l'unità prevalente
            if dati['unita'] == 'kwh':
                conta_kwh += 1
                unita_rilevata = 'kwh'
            elif dati['unita'] in ['smc', 'mc']:
                conta_smc += 1
                unita_rilevata = 'smc'

            record = {
                'data_sort': data_obj,
                'display': display if display else nome_file,
                'lordo': dati['lordo'], 'rai': dati['rai'], 'netto': dati['netto'],
                'consumo': dati['consumo'], 'unita': dati['unita'], 'msg': dati['msg'],
                'nome_file': nome_file
            }
            temp_list.append(record)

        # LOGICA TIPO BOLLETTA (LUCE vs GAS)
        if conta_kwh > conta_smc:
            self.tipo_bolletta = "Luce"
        elif conta_smc > 0:
            self.tipo_bolletta = "Gas"
        else:
            self.tipo_bolletta = "Bollette"
            
        # ORDINAMENTO
        self.dati_ordinati = sorted(temp_list, key=lambda x: x['data_sort'])

        # POPOLAMENTO GUI
        somma_netta = 0.0
        somma_consumi = 0.0
        somma_rai = 0.0

        for rec in self.dati_ordinati:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(rec['display']))
            self.table.setItem(row, 1, QTableWidgetItem(f"€ {rec['lordo']:.2f}"))
            
            item_rai = QTableWidgetItem(f"€ {rec['rai']:.2f}")
            if rec['rai'] > 0: item_rai.setForeground(QColor("#C0392B")) 
            self.table.setItem(row, 2, item_rai)
            
            item_netto = QTableWidgetItem(f"€ {rec['netto']:.2f}")
            item_netto.setFont(QFont("Arial", weight=QFont.Weight.Bold))
            self.table.setItem(row, 3, item_netto)
            
            consumo_str = f"{rec['consumo']} {rec['unita']}" if rec['consumo'] > 0 else "---"
            self.table.setItem(row, 4, QTableWidgetItem(consumo_str))
            
            p_unit = rec['netto'] / rec['consumo'] if rec['consumo'] > 0 else 0
            item_prz = QTableWidgetItem(f"€ {p_unit:.3f}")
            item_prz.setForeground(QColor("#2980B9")) 
            self.table.setItem(row, 5, item_prz)
            
            self.table.setItem(row, 6, QTableWidgetItem(rec['nome_file']))

            somma_netta += rec['netto']
            somma_consumi += rec['consumo']
            somma_rai += rec['rai']

        if trovato_rai: self.table.setColumnHidden(2, False)

        # Statistiche
        self.lbl_totale_soldi.setText(f"€ {somma_netta:.2f}")
        self.lbl_totale_consumi.setText(f"{somma_consumi:.1f} {unita_rilevata}")
        self.lbl_totale_rai.setText(f"€ {somma_rai:.2f}")
        
        avg_cost = somma_netta / len(self.dati_ordinati) if self.dati_ordinati else 0
        self.lbl_media_spesa.setText(f"€ {avg_cost:.2f}")

        if somma_consumi > 0:
            glob_avg = somma_netta / somma_consumi
            self.lbl_prezzo_medio.setText(f"€ {glob_avg:.3f} / {unita_rilevata}")

        self.aggiorna_grafici(self.dati_ordinati, unita_rilevata)
        print("Analisi completata.")

    def aggiorna_grafici(self, dati, unita):
        if not dati: return

        labels = [d['display'] for d in dati]
        valori_soldi = [d['netto'] for d in dati]
        valori_consumi = [d['consumo'] for d in dati]

        # 1. Grafico Costi
        ax_costi = self.canvas_costi.axes
        ax_costi.clear()
        bars = ax_costi.bar(labels, valori_soldi, color='#2ECC71', alpha=0.8) 
        ax_costi.set_title('Andamento Costi Netti (€)', fontsize=14, fontweight='bold', color='#333')
        ax_costi.grid(True, axis='y', linestyle='--', alpha=0.5)
        ax_costi.tick_params(axis='x', rotation=30, labelsize=10)
        ax_costi.bar_label(bars, fmt='€ %.0f', padding=3)
        self.canvas_costi.draw()

        # 2. Grafico Consumi
        ax_cons = self.canvas_consumi.axes
        ax_cons.clear()
        ax_cons.plot(labels, valori_consumi, marker='o', linestyle='-', color='#3498DB', linewidth=3) 
        ax_cons.fill_between(labels, valori_consumi, color='#3498DB', alpha=0.1)
        ax_cons.set_title(f'Andamento Consumi ({unita})', fontsize=14, fontweight='bold', color='#333')
        ax_cons.grid(True, linestyle='--', alpha=0.5)
        ax_cons.tick_params(axis='x', rotation=30, labelsize=10)
        for i, txt in enumerate(valori_consumi):
            ax_cons.annotate(f"{txt}", (labels[i], valori_consumi[i]), textcoords="offset points", xytext=(0,10), ha='center', fontweight='bold', color='#2C3E50')
        self.canvas_consumi.draw()

    # --- LOGICHE DI ESTRAZIONE ---
    def estrai_testo(self, path):
        full_text = ""
        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages):
                    if i >= 2: break
                    full_text += page.extract_text() + "\n"
        except Exception as e:
            print(f"Errore lettura {path}: {e}")
        return full_text

    def converti_numero(self, s):
        try: return float(s.replace('.','').replace(',','.'))
        except: return 0.0

    def estrai_data_competenza(self, testo):
        nomi_mesi = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
        
        pat_periodo = re.compile(r"PERIODO\s+BOLLETTA\s*(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})", re.IGNORECASE)
        match_periodo = pat_periodo.search(testo)
        if match_periodo:
            try:
                d1, m1, y1 = match_periodo.group(1).split('.')
                return date(int(y1), int(m1), int(d1)), f"{nomi_mesi[int(m1)]} {y1}"
            except: pass

        pat_range = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\s*(?:al|-)\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", re.IGNORECASE)
        match_range = pat_range.search(testo)
        if match_range:
            d, m, y = match_range.group(1), match_range.group(2), match_range.group(3)
            if len(y) == 2: y = "20" + y
            try:
                return date(int(y), int(m), int(d)), f"{nomi_mesi[int(m)]} {y}"
            except: pass

        mesi_dict = {m.lower(): i for i, m in enumerate(nomi_mesi) if m}
        pat_mese = re.compile(r"\b(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(20\d{2})\b", re.IGNORECASE)
        match = pat_mese.search(testo)
        if match:
            nm = match.group(1).lower()
            anno = match.group(2)
            idx = mesi_dict[nm]
            return date(int(anno), idx, 1), f"{nm.capitalize()} {anno}"

        return date(2999,1,1), None

    def estrai_dati_completi(self, testo):
        regex_totale = re.compile(r"(totale da pagare|totale bolletta|totale fattura|importo totale|totale spesa).*?(\d{1,4}[.,]\d{2})", re.IGNORECASE)
        match_list = regex_totale.findall(testo)
        val_lordo = max([self.converti_numero(m[1]) for m in match_list]) if match_list else 0.0
        
        regex_rai = re.compile(r"(canone\s+(rai|tv|abbonamento)).*?(\d{1,3}[.,]\d{2})", re.IGNORECASE)
        m_rai = regex_rai.search(testo)
        val_rai = self.converti_numero(m_rai.group(3)) if m_rai else 0.0
        if val_rai >= val_lordo: val_rai = 0.0
        
        consumo = 0.0
        unita = "?"
        msg = "OK"

        reg_gas_pulsee = re.compile(r"CONSUMI\s+FATTURATI\s+IN\s+TOTALE.*?IN\s+QUESTA\s+BOLLETTA:?\s*(\d+[.,]\d+)\s*(smc|mc|kwh)", re.DOTALL | re.IGNORECASE)
        m_gas = reg_gas_pulsee.search(testo)

        reg_std = re.compile(r"(?:consumi\s+fatturati|consumo\s+totale|totale\s+consumi).*?(\d{1,5}(?:[.,]\d{1,2})?)\s*(kwh|smc|mc)", re.IGNORECASE | re.DOTALL)
        m_std = reg_std.search(testo)
        
        if m_gas:
            consumo = self.converti_numero(m_gas.group(1))
            unita = m_gas.group(2).lower()
            msg = "Gas Pulsee"
        elif m_std:
            consumo = self.converti_numero(m_std.group(1))
            unita = m_std.group(2).lower()
            msg = "Standard"
        else:
            reg_fasce = re.compile(r"F1.*?(\d+[.,]\d+).*?F2.*?(\d+[.,]\d+).*?F3.*?(\d+[.,]\d+)", re.DOTALL | re.IGNORECASE)
            m_fasce = reg_fasce.search(testo)
            if m_fasce:
                 f1 = self.converti_numero(m_fasce.group(1))
                 f2 = self.converti_numero(m_fasce.group(2))
                 f3 = self.converti_numero(m_fasce.group(3))
                 if f1+f2+f3 > 0:
                     consumo = f1 + f2 + f3
                     unita = "kwh"
                     msg = "Somma Fasce"
            else:
                 msg = "N.D."

        if unita == "mc": unita = "smc"

        return {"lordo": val_lordo, "rai": val_rai, "netto": val_lordo-val_rai, "consumo": consumo, "unita": unita, "msg": msg}

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnalizzatoreBollette()
    window.showMaximized()
    sys.exit(app.exec())