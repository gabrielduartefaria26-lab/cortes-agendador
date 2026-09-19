"""Publica no Instagram os cortes cuja hora ja chegou.

Le agenda.json, publica o que venceu e ainda nao foi publicado, e registra
o resultado em estado.json. Roda a cada 15 minutos pelo GitHub Actions.
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

API = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["IG_TOKEN"]
IG_ID = os.environ["IG_USER_ID"]
BASE_URL = os.environ["VIDEOS_BASE_URL"].rstrip("/")
# Ensaio: monta o container na Meta e para antes de publicar. Valida token,
# permissoes e download do video sem postar nada no perfil.
ENSAIO = os.environ.get("ENSAIO") == "1"


def chamar(caminho, dados=None):
    url = f"{API}/{caminho}"
    corpo = None
    if dados is not None:
        dados = {**dados, "access_token": TOKEN}
        corpo = urllib.parse.urlencode(dados).encode()
    else:
        url += f"?access_token={TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, data=corpo), timeout=90) as r:
        return json.load(r)


def publicar(item):
    video_url = f"{BASE_URL}/{urllib.parse.quote(item['arquivo'])}"
    print(f"  container: {video_url}")
    container = chamar(f"{IG_ID}/media", {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": item["legenda"],
        "share_to_feed": "true",
    })["id"]

    # o Instagram baixa e transcodifica antes de aceitar a publicacao.
    # Reels de ate 90s costumam ficar prontos em 1 a 3 minutos.
    for tentativa in range(40):
        time.sleep(15)
        st = chamar(f"{container}?fields=status_code,status")
        if st["status_code"] == "FINISHED":
            break
        if st["status_code"] == "ERROR":
            raise RuntimeError(f"processamento falhou: {st.get('status')}")
        print(f"  {st['status_code']} ({(tentativa+1)*15}s)")
    else:
        raise RuntimeError("processamento passou de 10 minutos")

    if ENSAIO:
        print("  ensaio: container pronto e aceito, nao vou publicar")
        return None
    return chamar(f"{IG_ID}/media_publish", {"creation_id": container})["id"]


def main():
    agenda = json.load(open("agenda.json"))
    estado = json.load(open("estado.json")) if os.path.exists("estado.json") else {}
    agora = datetime.now(timezone.utc)

    pendente = lambda i: estado.get(i["id"], {}).get("status") != "publicado"
    vencidos = [i for i in agenda
                if (ENSAIO or datetime.fromisoformat(i["quando"]) <= agora)
                and pendente(i)]
    if not vencidos:
        print("nada a publicar")
        return 0

    houve_erro = False
    # um por execucao: se dois vencerem juntos, o segundo sai no ciclo seguinte,
    # 15 minutos depois. Evita estourar o limite da API num acumulo de atraso.
    item = vencidos[0]
    print(f"publicando {item['id']} (agendado para {item['quando']})")
    try:
        media_id = publicar(item)
        if ENSAIO:
            print("  ensaio concluido, estado nao foi alterado")
            return 0
        estado[item["id"]] = {"status": "publicado", "media_id": media_id,
                              "em": agora.isoformat(timespec="seconds")}
        print(f"  ok, media {media_id}")
    except Exception as e:
        anterior = estado.get(item["id"], {}).get("tentativas", 0)
        estado[item["id"]] = {"status": "erro", "erro": str(e),
                              "tentativas": anterior + 1,
                              "em": agora.isoformat(timespec="seconds")}
        print(f"  FALHOU: {e}", file=sys.stderr)
        houve_erro = True

    json.dump(estado, open("estado.json", "w"), ensure_ascii=False, indent=2)
    if len(vencidos) > 1:
        print(f"{len(vencidos)-1} ainda na fila, saem nos proximos ciclos")
    return 1 if houve_erro else 0


if __name__ == "__main__":
    sys.exit(main())
