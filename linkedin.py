"""Publica no LinkedIn (perfil pessoal) os carrosseis que ja venceram, como documento PDF.

So entra na fila o item da agenda que tem "pdf" (os carrosseis; os posts estilo tweet
ficam so no Instagram). O resultado vai para estado.json com a chave "li:<id>".
Le o PDF do mesmo release dos videos (VIDEOS_BASE_URL).

Ensaio (LI_ENSAIO=1): descobre o perfil e sobe o documento, mas nao cria o post.
O token do LinkedIn vence em 60 dias: quando vencer, o userinfo falha com 401 e o log diz.
"""
import json, os, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

TOKEN = os.environ["LINKEDIN_TOKEN"]
BASE_URL = os.environ["VIDEOS_BASE_URL"].rstrip("/")
ENSAIO = os.environ.get("LI_ENSAIO") == "1"
ENSAIO_ID = os.environ.get("LI_ENSAIO_ID", "")
# a API versionada aceita versoes de ate ~1 ano; tenta da mais nova para a mais velha
VERSOES = ["202609", "202606", "202603", "202601", "202510"]


def http(metodo, url, corpo=None, cabecalhos=None, bruto=False):
    h = {"Authorization": f"Bearer {TOKEN}", **(cabecalhos or {})}
    dados = None
    if corpo is not None:
        dados = corpo if bruto else json.dumps(corpo).encode()
        if not bruto:
            h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=dados, headers=h, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            texto = r.read().decode("utf-8", "replace")
            return r.status, dict(r.headers), (json.loads(texto) if texto.strip().startswith("{") else texto)
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", "replace").replace(TOKEN, "***")
        return erro.code, dict(erro.headers), detalhe


def rest(metodo, caminho, corpo=None):
    # descobre uma versao aceita na primeira chamada e reusa
    for v in ([rest.versao] if getattr(rest, "versao", None) else VERSOES):
        st, hd, resp = http(metodo, f"https://api.linkedin.com/rest/{caminho}", corpo,
                            {"LinkedIn-Version": v, "X-Restli-Protocol-Version": "2.0.0"})
        if st == 426 or "NONEXISTENT_VERSION" in str(resp) or "VERSION_MISSING" in str(resp):
            continue
        rest.versao = v
        if st >= 300:
            raise RuntimeError(f"{st} em {caminho}: {str(resp)[:500]}")
        return hd, resp
    raise RuntimeError("nenhuma versao da API aceita")


def autor():
    st, _, resp = http("GET", "https://api.linkedin.com/v2/userinfo")
    if st != 200:
        raise RuntimeError(f"{st} no userinfo (token vencido ou sem openid/profile?): {str(resp)[:300]}")
    return f"urn:li:person:{resp['sub']}"


def escapar(texto):
    # o campo commentary usa o formato "little text": esses caracteres precisam de barra
    for c in "\\|{}@[]()<>*_~":
        texto = texto.replace(c, "\\" + c)
    return texto


def publicar(item, dono):
    url = f"{BASE_URL}/{urllib.parse.quote(item['pdf'])}"
    print(f"  pdf: {url}")
    with urllib.request.urlopen(url, timeout=120) as r:
        pdf = r.read()

    _, ini = rest("POST", "documents?action=initializeUpload",
                  {"initializeUploadRequest": {"owner": dono}})
    destino, doc = ini["value"]["uploadUrl"], ini["value"]["document"]
    st, _, resp = http("PUT", destino, pdf, {"Content-Type": "application/octet-stream"}, bruto=True)
    if st >= 300:
        raise RuntimeError(f"{st} no upload do pdf: {str(resp)[:300]}")
    print(f"  documento: {doc}")
    if ENSAIO:
        print("  ensaio: documento aceito, nao vou criar o post")
        return None

    titulo = item.get("titulo_li") or item["legenda"].split("\n")[0][:120]
    hd, _ = rest("POST", "posts", {
        "author": dono,
        "commentary": escapar(item["legenda"]),
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                         "thirdPartyDistributionChannels": []},
        "content": {"media": {"title": titulo, "id": doc}},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    })
    return hd.get("x-restli-id") or hd.get("X-RestLi-Id") or "ok"


def main():
    agenda = json.load(open("agenda.json"))
    estado = json.load(open("estado.json")) if os.path.exists("estado.json") else {}
    agora = datetime.now(timezone.utc)

    carrosseis = [i for i in agenda if i.get("pdf")]
    if ENSAIO and ENSAIO_ID:
        fila = [i for i in carrosseis if i["id"] == ENSAIO_ID]
    else:
        fila = [i for i in carrosseis
                if (ENSAIO or datetime.fromisoformat(i["quando"]) <= agora)
                and estado.get("li:" + i["id"], {}).get("status") != "publicado"
                and estado.get("li:" + i["id"], {}).get("tentativas", 0) < 5]
    if not fila:
        print("linkedin: nada a publicar")
        return 0

    item = fila[0]
    print(f"linkedin: publicando {item['id']} (agendado para {item['quando']})")
    chave = "li:" + item["id"]
    try:
        post = publicar(item, autor())
        if ENSAIO:
            print("  ensaio concluido, estado nao foi alterado")
            return 0
        estado[chave] = {"status": "publicado", "post": post, "em": agora.isoformat(timespec="seconds")}
        print(f"  ok, post {post}")
        erro = False
    except Exception as e:
        anterior = estado.get(chave, {}).get("tentativas", 0)
        estado[chave] = {"status": "erro", "erro": str(e), "tentativas": anterior + 1,
                         "em": agora.isoformat(timespec="seconds")}
        print(f"  FALHOU: {e}", file=sys.stderr)
        erro = True
    json.dump(estado, open("estado.json", "w"), ensure_ascii=False, indent=2)
    return 1 if erro else 0


if __name__ == "__main__":
    sys.exit(main())
