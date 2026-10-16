"""Puxa os numeros de todos os posts do @system.oasis e grava em metricas.csv.

Roda uma vez por dia pelo GitHub Actions. Pega TODOS os posts da conta, inclusive os
publicados a mao pelo app (meme, tutorial), e nao so os que sairam pelo agendador.

O que cada post e (formato, gancho, fonte, versao do teste) vem da agenda: post que saiu
pelo agendador ja nasce classificado. Post publicado a mao pelo app se classifica em
classificacao.json, pelo media_id.

Gancho e o texto de abertura na tela (headline do carrossel, hook do video), nao a
legenda.

Precisa da permissao instagram_manage_insights no token. Sem ela a lista de posts sai,
mas as colunas de alcance, salvamento e compartilhamento ficam vazias.
"""
import csv, json, os, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

API = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["IG_TOKEN"]
IG_ID = os.environ["IG_USER_ID"]
SAIDA = "metricas.csv"

# o que a planilha mostra, nessa ordem
COLUNAS = ["data_postagem", "formato", "fonte", "cta", "versao", "tipo", "alcance", "views",
           "curtidas", "comentarios", "salvamentos", "compartilhamentos", "interacoes",
           "taxa_salvamento", "gancho", "link", "media_id", "atualizado", "tempo_medio_s"]


def chamar(caminho, params=None):
    params = {**(params or {}), "access_token": TOKEN}
    url = f"{API}/{caminho}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace").replace(TOKEN, "***")
        raise RuntimeError(f"{e.code}: {corpo[:240]}") from None


def todos_os_posts():
    campos = "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count"
    posts, pagina = [], chamar(f"{IG_ID}/media", {"fields": campos, "limit": 50})
    while True:
        posts += pagina.get("data", [])
        prox = pagina.get("paging", {}).get("next")
        if not prox:
            return posts
        with urllib.request.urlopen(prox, timeout=60) as r:
            pagina = json.load(r)


def brasilia(ts):
    # a API devolve "2026-09-21T12:00:03+0000"
    t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone(timedelta(hours=-3)))
    return t.strftime("%d/%m/%Y %H:%M")


def insights(media_id, produto):
    # Reel e carrossel aceitam conjuntos diferentes; pede um por um para que uma
    # metrica recusada nao derrube as outras.
    pedidas = ["reach", "saved", "shares", "total_interactions", "views"]
    if produto == "REELS":
        pedidas.append("ig_reels_avg_watch_time")  # 06/10: retencao, em milissegundos
    achou = {}
    for m in pedidas:
        try:
            d = chamar(f"{media_id}/insights", {"metric": m})
            valor = d["data"][0].get("values", [{}])[0].get("value")
            if valor is None:
                valor = d["data"][0].get("total_value", {}).get("value")
            achou[m] = valor
        except RuntimeError as e:
            if "(#10)" in str(e) or "permission" in str(e).lower():
                return None  # sem a permissao de insights: nao adianta insistir
            achou[m] = ""
    return achou


def catalogo():
    """O que se sabe de cada post que saiu pelo agendador, indexado pelo media_id."""
    try:
        estado = json.load(open("estado.json"))
        agenda = {i["id"]: i for i in json.load(open("agenda.json"))}
    except FileNotFoundError:
        return {}
    saida = {}
    for pid, e in estado.items():
        if e.get("status") != "publicado" or not e.get("media_id"):
            continue
        item = agenda.get(pid, {})
        saida[e["media_id"]] = {
            "formato": item.get("formato") or ("ferramenta" if pid.startswith("repos") else "case"),
            "gancho": item.get("gancho", ""),
            "fonte": "agendador",
            "cta": item.get("cta", ""),
            "versao": item.get("versao", ""),
        }
    try:
        for mid, c in json.load(open("classificacao.json")).items():
            saida.setdefault(mid, {"fonte": "app", "cta": "", "versao": "", **c})
    except FileNotFoundError:
        pass
    return saida


def main():
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    cat = catalogo()
    linhas, sem_permissao = [], False
    for p in todos_os_posts():
        ins = None if sem_permissao else insights(p["id"], p.get("media_product_type"))
        if ins is None:
            sem_permissao = True
            ins = {}
        c = cat.get(p["id"], {"formato": "manual", "gancho": "", "fonte": "app", "cta": "", "versao": ""})
        alcance = ins.get("reach") or 0
        salvos = ins.get("saved") or 0
        linhas.append({
            # hora de Brasilia, no formato que a planilha em portugues le como data
            "data_postagem": brasilia(p["timestamp"]),
            "_ordem": p["timestamp"],
            **c,
            "tipo": (p.get("media_product_type") or p.get("media_type") or "").lower(),
            "alcance": ins.get("reach", ""), "views": ins.get("views", ""),
            "curtidas": p.get("like_count", ""), "comentarios": p.get("comments_count", ""),
            "salvamentos": ins.get("saved", ""), "compartilhamentos": ins.get("shares", ""),
            "interacoes": ins.get("total_interactions", ""),
            "taxa_salvamento": f"{salvos / alcance:.3f}" if alcance else "",
            "link": p.get("permalink", ""), "media_id": p["id"], "atualizado": agora,
            "tempo_medio_s": f"{ins['ig_reels_avg_watch_time'] / 1000:.1f}" if ins.get("ig_reels_avg_watch_time") else "",
        })

    linhas.sort(key=lambda x: x.pop("_ordem"), reverse=True)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    print(f"{len(linhas)} posts gravados em {SAIDA}")
    if sem_permissao:
        print("AVISO: o token nao tem instagram_manage_insights. Lista saiu, numeros nao.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
