"""Test del parsing puro (stdlib-only, senza GUI)."""
from datetime import date

from bollettachiara import parser
from bollettachiara.versioni import confronta_versioni, parse_versione


def test_converti_numero_formato_italiano():
    assert parser.converti_numero("1.234,56") == 1234.56
    assert parser.converti_numero("12,5") == 12.5
    assert parser.converti_numero("abc") is None
    assert parser.converti_numero(None) is None


def test_estrai_data_periodo_bolletta():
    testo = "PERIODO BOLLETTA 01.03.2024 - 31.03.2024"
    d, label = parser.estrai_data_competenza(testo)
    assert d == date(2024, 3, 1)
    assert label == "Marzo 2024"


def test_estrai_data_fatturazione_numerica():
    testo = "Periodo di fatturazione: dal 5/2/2024 al 5/3/2024"
    d, label = parser.estrai_data_competenza(testo)
    assert d == date(2024, 2, 5)
    assert label == "Febbraio 2024"


def test_estrai_data_riferimento_eni_testuale():
    testo = "Periodo di riferimento da 3 Febbraio 2018 a 23 Marzo 2018"
    d, label = parser.estrai_data_competenza(testo)
    assert d == date(2018, 2, 3)
    assert label == "Febbraio 2018"


def test_estrai_data_periodo_mesi_enel():
    testo = "Periodo di riferimento gennaio - febbraio 2014"
    d, label = parser.estrai_data_competenza(testo)
    assert d == date(2014, 1, 1)
    assert label == "Gennaio 2014"


def test_estrai_data_nessun_match_ritorna_none():
    d, label = parser.estrai_data_competenza("nessuna data qui")
    assert d is None
    assert label is None


def test_estrai_dati_bolletta_enel():
    testo = """
    Totale da pagare 123,45 €
    Canone RAI 90,00 €
    Consumo Fatturato kWh 379
    """
    dati = parser.estrai_dati_completi(testo)
    assert dati["lordo"] == 123.45
    assert dati["rai"] == 90.00
    assert dati["netto"] == round(123.45 - 90.00, 2)
    assert dati["consumo"] == 379.0
    assert dati["unita"] == "kwh"


def test_estrai_dati_bolletta_gas_pulsee():
    testo = "CONSUMI FATTURATI IN TOTALE ... IN QUESTA BOLLETTA: 136,0 smc Totale bolletta 246,67"
    dati = parser.estrai_dati_completi(testo)
    assert dati["consumo"] == 136.0
    assert dati["unita"] == "smc"
    assert dati["lordo"] == 246.67


def test_estrai_dati_bolletta_ascotrade_senza_unita():
    testo = "TOTALE CONSUMO FATTURATO 400,00 ... Euro/Kwh ... Totale da pagare 100,00"
    dati = parser.estrai_dati_completi(testo)
    assert dati["consumo"] == 400.0
    assert dati["unita"] == "kwh"


def test_estrai_dati_bolletta_somma_fasce():
    testo = "F1 10,5 F2 20,5 F3 30,0 Totale da pagare 50,00"
    dati = parser.estrai_dati_completi(testo)
    assert dati["consumo"] == 61.0
    assert dati["unita"] == "kwh"
    assert dati["msg"] == "Somma Fasce"


def test_estrai_dati_bolletta_nessun_dato():
    dati = parser.estrai_dati_completi("testo senza campi utili")
    assert dati["lordo"] == 0.0
    assert dati["msg"] == "N.D."


def test_rai_maggiore_del_lordo_azzerato():
    testo = "Totale da pagare 50,00 Canone RAI 999,00"
    dati = parser.estrai_dati_completi(testo)
    assert dati["rai"] == 0.0


def test_bolletta_duale_engie():
    testo = """
    IMPORTO DA PAGARE 491,05 €
    TOTALE FORNITURA SALVO CONGUAGLIO € 246,67
    CONSUMO GAS 136 smc
    CONSUMO LUCE 461 kWh
    Canone RAI 90,00
    """
    dati = parser.estrai_dati_bolletta(testo)
    assert len(dati) == 2
    gas, luce = dati
    assert gas["unita"] == "smc" and gas["consumo"] == 136.0
    assert luce["unita"] == "kwh" and luce["consumo"] == 461.0
    assert luce["lordo"] == round(491.05 - 246.67, 2)


def test_bolletta_duale_eni():
    testo = """
    CONSUMO GAS ... CONSUMO LUCE
    Totale gas** 99,41 €
    Totale fornitura gas smc 127
    Totale luce** 75,55 €
    Totale fornitura luce kWh 393
    Canone di abbonamento RAI 90,00
    """
    dati = parser.estrai_dati_bolletta(testo)
    assert len(dati) == 2
    gas, luce = dati
    assert gas["lordo"] == 99.41 and gas["consumo"] == 127.0
    assert luce["netto"] == 75.55 and luce["rai"] == 90.00
    assert luce["consumo"] == 393.0


def test_record_energia_avvisi_periodo_mancante():
    records = parser.estrai_record_energia("Totale da pagare 10,00", "bolletta.pdf")
    assert len(records) == 1
    assert records[0].data_sort is None
    assert records[0].incerto
    assert any("periodo" in a for a in records[0].avvisi)


def test_record_energia_completo_non_incerto():
    testo = "PERIODO BOLLETTA 01.01.2024 - 31.01.2024 Totale da pagare 80,00 Consumo fatturato kWh 200"
    records = parser.estrai_record_energia(testo, "b.pdf")
    assert not records[0].incerto
    assert records[0].data_sort == date(2024, 1, 1)


def test_classifica_tipo():
    class R:
        def __init__(self, u):
            self.unita = u
    assert parser.classifica_tipo([R("kwh"), R("smc")]) == "Luce e Gas"
    assert parser.classifica_tipo([R("kwh")]) == "Luce"
    assert parser.classifica_tipo([R("smc")]) == "Gas"
    assert parser.classifica_tipo([]) == "Bollette"


def test_ats_valida():
    testo = """
    Periodo di fatturazione: dal 01/01/2024 al 31/01/2024
    Totale da pagare 45,50 Euro
    Totale Consumi fatturati: 30
    """
    rec = parser.analizza_ats_testo(testo, "ats.pdf")
    assert rec is not None
    assert rec.giorni == 31
    assert rec.importo == 45.50
    assert rec.mc == 30.0
    assert rec.costo_die == 45.50 / 31
    assert not rec.avvisi


def test_ats_senza_periodo():
    assert parser.analizza_ats_testo("niente", "x.pdf") is None
    assert parser.analizza_ats_testo("", "x.pdf") is None


def test_ats_periodo_invalido_avviso():
    testo = """
    Periodo di fatturazione: dal 31/01/2024 al 01/01/2024
    Totale da pagare 10,00 Euro
    Totale Consumi fatturati: 5
    """
    rec = parser.analizza_ats_testo(testo, "ats.pdf")
    assert rec is not None
    assert rec.giorni == 0
    assert any("giorni" in a for a in rec.avvisi)


def test_versioni_parse():
    assert parse_versione("v1.2.3") == (1, 2, 3)
    assert parse_versione("1.2") == (1, 2, 0)
    assert parse_versione("abc") is None
    assert parse_versione("") is None


def test_versioni_confronto():
    assert confronta_versioni("1.3.0", "1.2.2")
    assert not confronta_versioni("1.2.2", "1.2.2")
    assert not confronta_versioni("1.2.1", "1.2.2")
    assert not confronta_versioni("bad", "1.2.2")
