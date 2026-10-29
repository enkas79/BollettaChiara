"""Parsing puro (stdlib-only) dei testi estratti dalle bollette PDF.

Questo modulo non dipende da PyQt6/matplotlib/pdfplumber: riceve il testo
già estratto e restituisce dataclass, così è testabile con pytest senza GUI.
Le schede (tab_energia, tab_acqua) si occupano solo di estrarre il testo
dai PDF e di presentare i risultati.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime

NOMI_MESI = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
             "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

_MESI_ALT = "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
_MESI_DICT = {m.lower(): i for i, m in enumerate(NOMI_MESI) if m}


def converti_numero(s):
    """Converte una stringa numerica in formato italiano (1.234,56) in float.

    Restituisce None se la stringa non è un numero valido (a differenza del
    vecchio comportamento che restituiva 0.0 silenziosamente).
    """
    try:
        return float(str(s).replace('.', '').replace(',', '.'))
    except (ValueError, TypeError):
        return None


@dataclass
class BollettaEnergia:
    """Un record di bolletta Luce/Gas pronto per tabella/grafici."""
    data_sort: date | None
    display: str
    lordo: float
    rai: float
    netto: float
    consumo: float
    unita: str
    msg: str
    nome_file: str
    avvisi: list = field(default_factory=list)

    @property
    def incerto(self):
        return self.data_sort is None or self.msg == "N.D." or self.lordo <= 0


@dataclass
class BollettaAcqua:
    """Un record di bolletta ATS (acqua)."""
    periodo: str
    data_fine: date
    giorni: int
    importo: float
    mc: float
    costo_die: float
    mc_die: float
    file: str
    avvisi: list = field(default_factory=list)


def estrai_data_competenza(testo):
    """Estrae (data_sort, etichetta) dal periodo di competenza della bolletta.

    Restituisce (None, None) se nessun formato è riconosciuto (prima
    restituiva la sentinella date(2999, 1, 1) che ordinava silenziosamente
    in fondo alla lista).
    """
    pat_periodo = re.compile(
        r"PERIODO\s+BOLLETTA\s*(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})",
        re.IGNORECASE)
    match_periodo = pat_periodo.search(testo)
    if match_periodo:
        try:
            d1, m1, y1 = match_periodo.group(1).split('.')
            return date(int(y1), int(m1), int(d1)), f"{NOMI_MESI[int(m1)]} {y1}"
        except (ValueError, IndexError):
            pass

    pat_fatturazione = re.compile(
        r"Periodo\s+di\s+fatturazione\s*:?\s*dal\s*(\d{1,2})[./](\d{1,2})[./](\d{2,4})"
        r"\s*al\s*(\d{1,2})[./](\d{1,2})[./](\d{2,4})",
        re.IGNORECASE)
    match_fatturazione = pat_fatturazione.search(testo)
    if match_fatturazione:
        d, m, y = (match_fatturazione.group(1), match_fatturazione.group(2),
                   match_fatturazione.group(3))
        try:
            return date(int(y), int(m), int(d)), f"{NOMI_MESI[int(m)]} {y}"
        except ValueError:
            pass

    pat_periodo_riferimento = re.compile(
        rf"Periodo\s+di\s+riferimento.{{0,40}}?da\s+(\d{{1,2}})\s+({_MESI_ALT})\s+(20\d{{2}})",
        re.IGNORECASE | re.DOTALL)
    match_periodo_riferimento = pat_periodo_riferimento.search(testo)
    if match_periodo_riferimento:
        gg = match_periodo_riferimento.group(1)
        nm = match_periodo_riferimento.group(2).lower()
        anno = match_periodo_riferimento.group(3)
        try:
            idx = _MESI_DICT[nm]
            return date(int(anno), idx, int(gg)), f"{nm.capitalize()} {anno}"
        except (KeyError, ValueError):
            pass

    pat_periodo_mese = re.compile(
        rf"Periodo(?:\s+di\s+riferimento)?\s+({_MESI_ALT})\s*[-–]?\s*(?:{_MESI_ALT})?\s+(20\d{{2}})",
        re.IGNORECASE)
    match_periodo_mese = pat_periodo_mese.search(testo)
    if match_periodo_mese:
        nm = match_periodo_mese.group(1).lower()
        anno = match_periodo_mese.group(2)
        try:
            idx = _MESI_DICT[nm]
            return date(int(anno), idx, 1), f"{nm.capitalize()} {anno}"
        except (KeyError, ValueError):
            pass

    pat_range = re.compile(
        r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\s*(?:al|-)\s*"
        r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})",
        re.IGNORECASE)
    match_range = pat_range.search(testo)
    if match_range:
        d, m, y = match_range.group(1), match_range.group(2), match_range.group(3)
        if len(y) == 2:
            y = "20" + y
        try:
            return date(int(y), int(m), int(d)), f"{NOMI_MESI[int(m)]} {y}"
        except ValueError:
            pass

    pat_mese = re.compile(rf"\b({_MESI_ALT})\s+(20\d{{2}})\b", re.IGNORECASE)
    match = pat_mese.search(testo)
    if match:
        nm = match.group(1).lower()
        anno = match.group(2)
        idx = _MESI_DICT[nm]
        return date(int(anno), idx, 1), f"{nm.capitalize()} {anno}"

    return None, None


def _estrai_dati_luce_gas_combinata(testo):
    """Bolletta unica stile ENGIE (luce + gas). Ritorna lista di dict o None."""
    m_importo = re.search(
        r"IMPORTO DA PAGARE.*?(\d{1,4}[.,]\d{2})\s*€", testo, re.DOTALL | re.IGNORECASE)
    m_gas_tot = re.search(
        r"TOTALE FORNITURA SALVO CONGUAGLIO\s*€?\s*(\d{1,4}[.,]\d{2})",
        testo, re.DOTALL | re.IGNORECASE)
    m_gas_smc = re.search(
        r"CONSUMO GAS.*?(\d+(?:[.,]\d+)?)\s*smc", testo, re.DOTALL | re.IGNORECASE)
    m_luce_kwh = re.search(
        r"CONSUMO LUCE.*?(\d+(?:[.,]\d+)?)\s*kWh", testo, re.DOTALL | re.IGNORECASE)

    if not (m_importo and m_gas_tot and m_gas_smc and m_luce_kwh):
        return _estrai_dati_luce_gas_eni(testo)

    importo_totale = converti_numero(m_importo.group(1)) or 0.0
    gas_totale = converti_numero(m_gas_tot.group(1)) or 0.0
    luce_totale = round(importo_totale - gas_totale, 2)

    m_rai = re.search(r"canone\s+(?:di\s+)?(rai|tv|abbonamento).*?(\d{1,3}[.,]\d{2})",
                      testo, re.IGNORECASE)
    rai = converti_numero(m_rai.group(2)) if m_rai else 0.0
    rai = rai or 0.0
    if rai >= luce_totale:
        rai = 0.0

    return [
        {"lordo": gas_totale, "rai": 0.0, "netto": gas_totale,
         "consumo": converti_numero(m_gas_smc.group(1)) or 0.0, "unita": "smc",
         "msg": "Gas (bolletta duale)"},
        {"lordo": luce_totale, "rai": rai, "netto": luce_totale - rai,
         "consumo": converti_numero(m_luce_kwh.group(1)) or 0.0, "unita": "kwh",
         "msg": "Luce (bolletta duale)"},
    ]


def _estrai_dati_luce_gas_eni(testo):
    """Bolletta unica stile Eni gas e luce (dettaglio pagina 2)."""
    m_gas_tot = re.search(r"Totale\s+gas\**\s*(\d{1,4}[.,]\d{2})\s*€", testo, re.IGNORECASE)
    m_gas_smc = re.search(r"Totale\s+fornitura\s+gas\s+smc\s*(\d+(?:[.,]\d+)?)", testo, re.IGNORECASE)
    m_luce_tot = re.search(r"Totale\s+luce\**\s*(\d{1,4}[.,]\d{2})\s*€", testo, re.IGNORECASE)
    m_luce_kwh = re.search(r"Totale\s+fornitura\s+luce\s+kWh\s*(\d+(?:[.,]\d+)?)", testo, re.IGNORECASE)

    if not (m_gas_tot and m_gas_smc and m_luce_tot and m_luce_kwh):
        return None

    gas_totale = converti_numero(m_gas_tot.group(1)) or 0.0
    luce_netto = converti_numero(m_luce_tot.group(1)) or 0.0

    m_rai = re.search(r"canone\s+(?:di\s+)?(rai|tv|abbonamento).*?(\d{1,3}[.,]\d{2})",
                      testo, re.IGNORECASE)
    rai = converti_numero(m_rai.group(2)) if m_rai else 0.0
    rai = rai or 0.0

    luce_totale = round(luce_netto + rai, 2)

    return [
        {"lordo": gas_totale, "rai": 0.0, "netto": gas_totale,
         "consumo": converti_numero(m_gas_smc.group(1)) or 0.0, "unita": "smc",
         "msg": "Gas (bolletta duale Eni)"},
        {"lordo": luce_totale, "rai": rai, "netto": luce_netto,
         "consumo": converti_numero(m_luce_kwh.group(1)) or 0.0, "unita": "kwh",
         "msg": "Luce (bolletta duale Eni)"},
    ]


def estrai_dati_bolletta(testo):
    """Lista di dict dati estratti (1 elemento normale, 2 per bollette duali)."""
    if re.search(r"CONSUMO GAS", testo, re.IGNORECASE) and re.search(r"CONSUMO LUCE", testo, re.IGNORECASE):
        dati_duali = _estrai_dati_luce_gas_combinata(testo)
        if dati_duali:
            return dati_duali
    return [estrai_dati_completi(testo)]


def estrai_dati_completi(testo):
    """Estrae lordo/rai/netto/consumo da una bolletta luce o gas singola."""
    regex_totale = re.compile(
        r"(totale da pagare|totale bolletta|totale fattura|importo totale|totale spesa)"
        r".*?(\d{1,4}[.,]\d{2})",
        re.IGNORECASE)
    match_list = regex_totale.findall(testo)
    valori = [converti_numero(m[1]) for m in match_list]
    valori = [v for v in valori if v is not None]
    val_lordo = max(valori) if valori else 0.0

    regex_rai = re.compile(r"(canone\s+(?:di\s+)?(rai|tv|abbonamento)).*?(\d{1,3}[.,]\d{2})", re.IGNORECASE)
    m_rai = regex_rai.search(testo)
    val_rai = converti_numero(m_rai.group(3)) if m_rai else None
    val_rai = val_rai if val_rai is not None else 0.0
    if val_rai >= val_lordo > 0:
        val_rai = 0.0

    consumo = 0.0
    unita = "?"
    msg = "OK"

    reg_gas_pulsee = re.compile(
        r"CONSUMI\s+FATTURATI\s+IN\s+TOTALE.*?IN\s+QUESTA\s+BOLLETTA:?\s*"
        r"(\d+[.,]\d+)\s*(smc|mc|kwh)",
        re.DOTALL | re.IGNORECASE)
    m_gas = reg_gas_pulsee.search(testo)

    reg_consumo_fatturato = re.compile(
        r"consumo\s+fatturato\s*(kwh|smc|mc)\D{0,15}(\d{1,5}(?:[.,]\d{1,2})?)",
        re.IGNORECASE | re.DOTALL)
    m_consumo_fatt = reg_consumo_fatturato.search(testo)

    reg_std = re.compile(
        r"(?:consumi\s+fatturati|consumo\s+totale|totale\s+consumi).*?"
        r"(\d{1,5}(?:[.,]\d{1,2})?)\s*(kwh|smc|mc)",
        re.IGNORECASE | re.DOTALL)
    m_std = reg_std.search(testo)

    reg_tot_fatturato = re.compile(
        r"totale\s+consumo\s+fatturato\D{0,5}(\d{1,5}[.,]\d{1,2})(.{0,80})",
        re.IGNORECASE | re.DOTALL)
    m_tot_fatt = reg_tot_fatturato.search(testo)

    if m_gas:
        consumo = converti_numero(m_gas.group(1)) or 0.0
        unita = m_gas.group(2).lower()
        msg = "Gas Pulsee"
    elif m_consumo_fatt:
        consumo = converti_numero(m_consumo_fatt.group(2)) or 0.0
        unita = m_consumo_fatt.group(1).lower()
        msg = "Consumo Fatturato"
    elif m_std:
        consumo = converti_numero(m_std.group(1)) or 0.0
        unita = m_std.group(2).lower()
        msg = "Standard"
    elif m_tot_fatt:
        consumo = converti_numero(m_tot_fatt.group(1)) or 0.0
        unita_match = re.search(r"kwh|smc|mc", m_tot_fatt.group(2), re.IGNORECASE)
        unita = unita_match.group(0).lower() if unita_match else "kwh"
        msg = "Totale Consumo Fatturato"
    else:
        reg_fasce = re.compile(r"F1.*?(\d+[.,]\d+).*?F2.*?(\d+[.,]\d+).*?F3.*?(\d+[.,]\d+)",
                               re.DOTALL | re.IGNORECASE)
        m_fasce = reg_fasce.search(testo)
        if m_fasce:
            f1 = converti_numero(m_fasce.group(1)) or 0.0
            f2 = converti_numero(m_fasce.group(2)) or 0.0
            f3 = converti_numero(m_fasce.group(3)) or 0.0
            if f1 + f2 + f3 > 0:
                consumo = f1 + f2 + f3
                unita = "kwh"
                msg = "Somma Fasce"
        if msg == "OK":
            msg = "N.D."

    if unita == "mc":
        unita = "smc"

    return {"lordo": val_lordo, "rai": val_rai, "netto": val_lordo - val_rai,
            "consumo": consumo, "unita": unita, "msg": msg}


def estrai_record_energia(testo, nome_file):
    """Costruisce la lista di BollettaEnergia da un testo PDF (1 o 2 record)."""
    data_obj, display = estrai_data_competenza(testo)
    records = []
    for dati in estrai_dati_bolletta(testo):
        avvisi = []
        if data_obj is None:
            avvisi.append("periodo non riconosciuto")
        if dati["lordo"] <= 0:
            avvisi.append("importo non trovato")
        if dati["consumo"] <= 0:
            avvisi.append("consumo non trovato")
        records.append(BollettaEnergia(
            data_sort=data_obj,
            display=display if display else nome_file,
            lordo=dati["lordo"], rai=dati["rai"], netto=dati["netto"],
            consumo=dati["consumo"], unita=dati["unita"], msg=dati["msg"],
            nome_file=nome_file, avvisi=avvisi,
        ))
    return records


def classifica_tipo(records):
    """Determina il tipo di bolletta ('Luce', 'Gas', 'Luce e Gas', 'Bollette')."""
    conta_kwh = sum(1 for r in records if r.unita == "kwh")
    conta_smc = sum(1 for r in records if r.unita in ("smc", "mc"))
    if conta_kwh > 0 and conta_smc > 0:
        return "Luce e Gas"
    if conta_kwh > conta_smc:
        return "Luce"
    if conta_smc > 0:
        return "Gas"
    return "Bollette"


def analizza_ats_testo(testo, nome_file):
    """Estrae un record BollettaAcqua dal testo di una bolletta ATS, o None."""
    if not testo:
        return None

    periodo_regex = re.search(
        r"Periodo\s+di\s+fatturazione\s*:\s*dal\s*(\d{2}/\d{2}/\d{4})\s*al\s*(\d{2}/\d{2}/\d{4})",
        testo, re.IGNORECASE)
    if not periodo_regex:
        return None

    try:
        d_inizio = datetime.strptime(periodo_regex.group(1), "%d/%m/%Y").date()
        d_fine = datetime.strptime(periodo_regex.group(2), "%d/%m/%Y").date()
    except ValueError:
        return None

    giorni = (d_fine - d_inizio).days + 1
    periodo_str = f"{d_inizio.strftime('%b')} - {d_fine.strftime('%b %Y')}"

    importo_regex = re.search(
        r"(?:Totale\s+da\s+pagare|Totale\s+bolletta).*?(\d+[.,]\d+)\s*Euro",
        testo, re.IGNORECASE | re.DOTALL)
    importo = converti_numero(importo_regex.group(1)) if importo_regex else None
    importo = importo if importo is not None else 0.0

    consumo_regex = re.search(
        r"Totale\s+Consumi\s+fatturati\s*[:\.]?\s*(\d+(?:[.,]\d+)?)", testo, re.IGNORECASE)
    consumo = converti_numero(consumo_regex.group(1)) if consumo_regex else None
    consumo = consumo if consumo is not None else 0.0

    avvisi = []
    if giorni <= 0:
        avvisi.append("periodo non valido (giorni <= 0)")
    if importo <= 0:
        avvisi.append("importo non trovato")
    if consumo <= 0:
        avvisi.append("consumo non trovato")

    return BollettaAcqua(
        periodo=periodo_str,
        data_fine=d_fine,
        giorni=giorni if giorni > 0 else 0,
        importo=importo,
        mc=consumo,
        costo_die=importo / giorni if giorni > 0 else 0.0,
        mc_die=consumo / giorni if giorni > 0 else 0.0,
        file=nome_file,
        avvisi=avvisi,
    )
