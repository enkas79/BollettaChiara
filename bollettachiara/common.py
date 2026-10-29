"""Utilità condivise tra le schede Energia (Luce/Gas) e Acqua.

Contiene l'estrazione testo PDF (con eccezioni, non più print silenziose),
il canvas Matplotlib, gli stili condivisi e l'export PDF di riepilogo
multi-pagina.
"""
import logging
from datetime import date
from pathlib import Path

import matplotlib
import pdfplumber

matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdf_canvas
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

log = logging.getLogger(__name__)


def estrai_testo(path, max_pagine=2):
    """Estrae il testo delle prime `max_pagine` pagine di un PDF.

    Solleva eccezioni in caso di file illeggibile: il chiamante (worker
    su thread separato) le intercetta e le riporta all'utente.
    """
    path = Path(path)
    full_text = ""
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= max_pagine:
                break
            full_text += (page.extract_text() or "") + "\n"
    return full_text


class MplCanvas(FigureCanvasQTAgg):
    """Canvas Matplotlib condiviso per i grafici costi/consumi."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        fig.tight_layout(pad=3.0)
        super().__init__(fig)


_PALETTE_PULSANTI = {
    "carica": ("#1565C0", "#0D47A1"),
    "esporta": ("#6A1B9A", "#4A148C"),
    "reset": ("#C62828", "#8E0000"),
}


def stile_pulsante(ruolo):
    """Restituisce lo stylesheet Qt per un pulsante, uniforme in tutte le schede."""
    colore, colore_hover = _PALETTE_PULSANTI[ruolo]
    return f"""
        QPushButton {{
            background-color: {colore};
            color: white;
            font-weight: bold;
            padding: 10px 16px;
            border-radius: 6px;
            font-size: 14px;
        }}
        QPushButton:hover {{
            background-color: {colore_hover};
        }}
    """


def crea_box_statistica(titolo, widget_valore, colore_testo, font_size="20px"):
    """Crea un box statistico stile card per la sidebar dei riepiloghi."""
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


def esporta_pdf_riepilogo(file_path, titolo_report, sezioni, colore_principale="#2E86C1",
                           footer_text="Documento generato da BollettaChiara"):
    """Genera un PDF di riepilogo A4 con header colorato e sezioni a righe.

    `sezioni` è una lista di tuple (nome_sezione, righe) dove righe è una
    lista di tuple (etichetta, valore, colore_valore_hex_o_None).
    Se il contenuto supera una pagina, continua su pagine aggiuntive
    ripetendo header e footer.
    """
    if not REPORTLAB_OK:
        raise RuntimeError("Libreria 'reportlab' mancante. Esegui 'pip install reportlab'.")

    c = pdf_canvas.Canvas(str(file_path), pagesize=A4)
    width, height = A4
    margine_inf = 70

    def nuova_pagina():
        c.setStrokeColor(colors.HexColor(colore_principale))
        c.setLineWidth(2)
        c.line(50, height - 50, width - 50, height - 50)
        c.setFont("Helvetica-Bold", 24)
        c.setFillColor(colors.HexColor(colore_principale))
        c.drawCentredString(width / 2, height - 90, titolo_report)
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.black)
        c.drawCentredString(width / 2, height - 110, f"Generato il: {date.today().strftime('%d/%m/%Y')}")
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.gray)
        c.drawCentredString(width / 2, 50, footer_text)

    def disegna_riga(y, etichetta, valore, colore_valore=colors.black):
        if y < margine_inf:
            c.showPage()
            nuova_pagina()
            y = height - 160
        c.setFillColor(colors.whitesmoke)
        c.rect(50, y - 5, width - 100, 30, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.darkslategray)
        c.drawString(70, y + 5, etichetta)
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colore_valore)
        c.drawRightString(width - 70, y + 5, str(valore))
        return y - 40

    nuova_pagina()
    y_pos = height - 160
    for nome_sezione, righe in sezioni:
        if y_pos - 60 < margine_inf:
            c.showPage()
            nuova_pagina()
            y_pos = height - 160
        c.setFillColor(colors.HexColor(colore_principale))
        c.rect(50, y_pos, width - 100, 25, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, y_pos + 7, nome_sezione)
        y_pos -= 40

        for etichetta, valore, colore_hex in righe:
            colore = colors.HexColor(colore_hex) if colore_hex else colors.black
            y_pos = disegna_riga(y_pos, etichetta, valore, colore)

        y_pos -= 20

    c.save()
