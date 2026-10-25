"""Scarica i calendari Lodgify (iCal) e salva le notti occupate in disponibilita.json.

Eseguito ogni ora dalla GitHub Action .github/workflows/sync-calendari.yml.
"""
import json
import re
import sys
import urllib.request
from datetime import date, timedelta

CALENDARI = {
    "oro": "https://www.lodgify.com/bd65ccef-a37b-46bd-b0cd-86683ef8a995.ics",
    "garden": "https://www.lodgify.com/c2bdeeab-b022-47cf-89c4-51733463bb5b.ics",
}


def scarica(url):
    req = urllib.request.Request(url, headers={"User-Agent": "gnsuiteroma-sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_data(valore):
    m = re.match(r"(\d{4})(\d{2})(\d{2})", valore.strip())
    if not m:
        return None
    return date(int(m[1]), int(m[2]), int(m[3]))


def notti_occupate(testo):
    # Riunisce le righe "piegate" dello standard iCal
    testo = re.sub(r"\r?\n[ \t]", "", testo)
    occupate = set()
    for blocco in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", testo, re.S):
        inizio = fine = None
        for riga in blocco.splitlines():
            if riga.startswith("DTSTART"):
                inizio = parse_data(riga.split(":", 1)[1])
            elif riga.startswith("DTEND"):
                fine = parse_data(riga.split(":", 1)[1])
        if not inizio:
            continue
        if not fine or fine <= inizio:
            fine = inizio + timedelta(days=1)
        # DTEND è il giorno di check-out: le notti occupate vanno da inizio a fine-1
        g = inizio
        while g < fine:
            occupate.add(g.isoformat())
            g += timedelta(days=1)
    oggi = date.today().isoformat()
    return sorted(d for d in occupate if d >= oggi)


def main():
    try:
        with open("disponibilita.json", encoding="utf-8") as f:
            precedente = json.load(f)
    except (OSError, ValueError):
        precedente = {}

    risultato = {}
    errori = 0
    for nome, url in CALENDARI.items():
        try:
            risultato[nome] = notti_occupate(scarica(url))
            print(f"{nome}: {len(risultato[nome])} notti occupate")
        except Exception as e:  # se Lodgify non risponde, tengo i dati vecchi
            errori += 1
            risultato[nome] = precedente.get(nome, [])
            print(f"{nome}: errore ({e}), mantengo i dati precedenti", file=sys.stderr)

    with open("disponibilita.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=1)
    if errori == len(CALENDARI):
        sys.exit(1)


if __name__ == "__main__":
    main()
