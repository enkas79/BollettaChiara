"""Dialoghi 'Informazioni' e 'Guida' del menu Aiuto, come richiesto da CLAUDE.md."""
from PyQt6.QtWidgets import QMessageBox

from .versioni import leggi_versione_locale

AUTORE = "Enkas79"


def mostra_informazioni(parent):
    versione = leggi_versione_locale() or "sconosciuta"
    QMessageBox.about(
        parent,
        "Informazioni su BollettaChiara",
        f"<h3>BollettaChiara</h3>"
        f"<p>Versione: {versione}</p>"
        f"<p>Autore: {AUTORE}</p>"
        f"<p>Analizzatore di bollette Luce, Gas e Acqua da PDF, con grafici "
        f"di andamento costi/consumi ed export riepilogo in PDF.</p>",
    )


def mostra_guida(parent):
    QMessageBox.information(
        parent,
        "Guida all'uso",
        "<h3>Come usare BollettaChiara</h3>"
        "<ol>"
        "<li>Seleziona la scheda del tipo di utenza (Luce/Gas o Acqua).</li>"
        "<li>Premi <b>Carica Bollette</b> e seleziona uno o più PDF.</li>"
        "<li>Consulta tabella, statistiche e grafici generati automaticamente.</li>"
        "<li>Premi <b>Salva Riepilogo PDF</b> per esportare un report riassuntivo.</li>"
        "<li>Usa <b>Reset</b> per svuotare i dati caricati nella scheda corrente.</li>"
        "</ol>"
        "<p>I dati vengono estratti dal testo dei PDF: se una bolletta ha un "
        "layout non riconosciuto, i campi mancanti sono evidenziati con ⚠ "
        "e segnalati in un avviso.</p>",
    )
