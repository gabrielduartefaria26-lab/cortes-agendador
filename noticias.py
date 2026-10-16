"""Pauta quente de vendas, comercial e gestão de time para o @gabrieldfaria_ (15/10/2026).

Roda 2x por dia no GitHub Actions e lê buscas do Google Notícias (Brasil e EUA). Grava em
quentes.json o que é novo: notícia com pessoa, empresa ou número que vire tema emocional com a
venda como moral. A escolha de virar post é do Gabriel, no quadro.

Novidade = link que não estava em vistos.json. Sai da lista depois de 7 dias.
"""
import json, os, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

UA = {"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/124"}
BR = "&hl=pt-BR&gl=BR&ceid=BR:pt-419"
US = "&hl=en-US&gl=US&ceid=US:en"
BUSCAS = [   # (tema, busca, região)
    ("time de vendas", '"time de vendas" OR "equipe comercial" OR "gestor comercial"', BR),
    ("meta e processo", '"meta de vendas" OR "metas comerciais" OR "processo comercial" OR "funil de vendas"', BR),
    ("empresas e varejo", 'varejo vendas faturamento empresa estratégia', BR),
    ("demissão e contratação", 'demite vendedores OR contrata vendedores OR "força de vendas"', BR),
    ("IA em vendas", '"inteligência artificial" vendas vendedor', BR),
    ("sales (EUA)", '"sales team" OR "sales reps" OR "sales quota"', US),
    ("AI sales (EUA)", '"AI SDR" OR "AI sales agent" OR "sales AI"', US),
]
VISTOS, QUENTES = "vistos.json", "quentes.json"


def itens():
    for tema, q, regiao in BUSCAS:
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:2d") + regiao
        try:
            raiz = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())
        except Exception as e:
            print("falhou", tema, str(e)[:80]); continue
        for it in list(raiz.iter("item"))[:15]:
            titulo, link = (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()
            fonte = (it.findtext("source") or "").strip()
            if titulo and link:
                yield tema, fonte, titulo, link


def main():
    agora = datetime.now(timezone.utc)
    primeira = not os.path.exists(VISTOS)
    vistos = set(json.load(open(VISTOS))) if not primeira else set()
    quentes = json.load(open(QUENTES)) if os.path.exists(QUENTES) else []
    titulos = {q["titulo"] for q in quentes}
    novos = []
    for tema, fonte, titulo, link in itens():
        if link in vistos or titulo in titulos: continue
        vistos.add(link); titulos.add(titulo)
        novos.append({"tema": tema, "fonte": fonte, "titulo": titulo, "link": link,
                      "visto_em": agora.isoformat(timespec="minutes")})
    corte = (agora - timedelta(days=7)).isoformat()
    quentes = [q for q in novos + quentes if q["visto_em"] >= corte]
    json.dump(sorted(vistos), open(VISTOS, "w"), ensure_ascii=False, indent=0)
    json.dump(quentes, open(QUENTES, "w"), ensure_ascii=False, indent=1)
    print(f"{len(novos)} novidade(s), {len(quentes)} na lista")
    for q in novos[:40]: print(" ·", q["tema"], "|", q["fonte"], "|", q["titulo"])


if __name__ == "__main__":
    main()
