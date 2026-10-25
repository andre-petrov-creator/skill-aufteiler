"""
Vision-Smoke-Test: kann Sonnet 4.6 die Dortmund-Mieterliste-PNG korrekt lesen?

Soll-Werte (aus manuellem quickcheck-log.md):
  - 11 WE
  - Wohnflächen: [80, 25, 70, 25, 70, 25, 70, 25, 70, 25, 70]
  - Summe IST-Miete: 51848.88 €/Jahr (ohne Leerstand-WE)
"""
import base64, json, os, sys
from pathlib import Path
from anthropic import Anthropic

PNG = Path(r"C:\Users\andre\OneDrive - APPV Personalvermittlung\Immobilien\001_AQUISE\Objekte\kleine-burgholzstr-5-dortmund\Mietaufstellung.png")
SOLL_WOHNFLAECHEN = [80, 25, 70, 25, 70, 25, 70, 25, 70, 25, 70]
SOLL_IST_MIETE_JAHR = 51848.88
TOLERANCE_PCT = 5.0  # ±5% akzeptiert

def main():
    img_b64 = base64.standard_b64encode(PNG.read_bytes()).decode()
    client = Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text":
                 "Diese Mieterliste enthält Wohnungen mit Wohnfläche (qm) "
                 "und IST-Miete (€/Monat kalt). Extrahiere als JSON:\n"
                 "{ 'wohnungen': [{'qm': float, 'ist_miete_eur_pro_monat': float}, ...] }\n"
                 "Nur das JSON-Objekt, keine Erklärung."}
            ]
        }]
    )
    text = resp.content[0].text.strip()
    # JSON evtl. in Markdown-Fence — strippen
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"): text = text[4:]
    data = json.loads(text)
    wohnungen = data["wohnungen"]

    print(f"Sonnet hat {len(wohnungen)} Wohnungen erkannt (Soll: 11)")
    qm_ist = sorted([w["qm"] for w in wohnungen])
    qm_soll = sorted(SOLL_WOHNFLAECHEN)
    print(f"Wohnflächen IST: {qm_ist}")
    print(f"Wohnflächen SOLL: {qm_soll}")

    summe_miete_monat = sum(w["ist_miete_eur_pro_monat"] for w in wohnungen)
    summe_miete_jahr = summe_miete_monat * 12
    diff_pct = abs(summe_miete_jahr - SOLL_IST_MIETE_JAHR) / SOLL_IST_MIETE_JAHR * 100
    print(f"IST-Miete/Jahr IST: {summe_miete_jahr:.2f} € (Soll: {SOLL_IST_MIETE_JAHR}, Diff: {diff_pct:.2f}%)")

    ok_count = (len(wohnungen) == 11)
    ok_qm = (qm_ist == qm_soll)
    ok_miete = (diff_pct <= TOLERANCE_PCT)
    print(f"\nResult: count={ok_count}, qm={ok_qm}, miete={ok_miete}")
    sys.exit(0 if (ok_count and ok_qm and ok_miete) else 1)

if __name__ == "__main__":
    main()
