"""Grava o total de seguidores do @gabrielfaria.ia em seguidores.csv (04/10/2026).

A Meta so libera o ganho diario de seguidores (insight follower_count) a partir de 100
seguidores, e nos Reels o insight "follows" por post nao existe. Entao a curva sai de uma
foto do total feita de hora em hora pelo GitHub Actions. O quadro (aba de analise) calcula
o saldo por dia e quanto cada post trouxe (do horario dele ate o post seguinte).

Grava so quando o numero muda ou quando a ultima linha tem mais de 6 h (curva sem buraco).
"""
import csv, json, os, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

API = "https://graph.facebook.com/v21.0"
ARQ = "seguidores.csv"
BRT = timezone(timedelta(hours=-3))

url = f"{API}/{os.environ['IG_USER_ID']}?" + urllib.parse.urlencode({"fields": "followers_count", "access_token": os.environ["IG_TOKEN"]})
with urllib.request.urlopen(url, timeout=60) as r:
    total = json.load(r)["followers_count"]

agora = datetime.now(BRT)
linhas = list(csv.DictReader(open(ARQ))) if os.path.exists(ARQ) else []
if linhas:
    ult = linhas[-1]; t_ult = datetime.strptime(ult["data"], "%d/%m/%Y %H:%M").replace(tzinfo=BRT)
    if int(ult["seguidores"]) == total and agora - t_ult < timedelta(hours=6):
        print(f"sem mudanca ({total})"); raise SystemExit
novo = not os.path.exists(ARQ)
with open(ARQ, "a", newline="") as f:
    w = csv.writer(f)
    if novo: w.writerow(["data", "seguidores", "fonte"])
    w.writerow([agora.strftime("%d/%m/%Y %H:%M"), total, "api"])
print("gravado", total)
