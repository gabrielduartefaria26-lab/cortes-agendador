"""Caça os Reels fora da curva dos perfis de referência e grava em outliers.csv.

Roda uma vez por semana pelo GitHub Actions. Fora da curva não é viral: é o Reel que fez
pelo menos 3 vezes a mediana de interação do PRÓPRIO perfil nos últimos posts. Assim um
perfil de 800 mil não esmaga um de 8 mil, e o que sobra é formato e tema que venceram, não
audiência que o perfil já tinha.

Usa business_discovery da API do Instagram: só funciona com perfil comercial ou de criador,
e devolve curtida e comentário, não visualização. Perfil pessoal ou que esconde curtida
aparece como pulado no log.

A lista de perfis mora em referencias.txt, um @ por linha (linha com # é comentário). Uma
linha "## nome" abre um grupo (ia, dono): o perfil herda o grupo, que vai para o CSV, para
separar o que funciona com quem ama IA do que funciona com empresário.
"""
import csv, json, os, statistics, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

API = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["IG_TOKEN"]
IG_ID = os.environ["IG_USER_ID"]
SAIDA = os.environ.get("SAIDA", "outliers.csv")
SAIDA_CARROSSEL = os.environ.get("SAIDA_CARROSSEL", "outliers-carrossel.csv")  # mesma passada, régua contra todos os posts do perfil
REFERENCIAS = os.environ.get("REFERENCIAS", "referencias.txt")
VEZES = 3.0          # quantas vezes a mediana do perfil para contar como fora da curva
JANELA_DIAS = 60     # formato mais velho que isso provavelmente já saturou
POSTS_POR_PERFIL = 40
MINIMO_PARA_MEDIANA = 8
MINIMO_INTERACOES = 100  # perfil com mediana 3 gera '8x' com 26 interações: isso é ruído
MEDIANA_MINIMA = 30      # abaixo disso a razão explode (o '1015x' de 24/09 era isso): perfil sai
VEZES_GRUPO = {"gabriel": 2.0}  # referências dele: régua mais baixa, entram mais Reels
VEZES_CARROSSEL = 1.5  # contra a mediana de TODOS os posts, Reel incluso: já é régua dura

COLUNAS = ["vezes_acima", "grupo", "perfil", "seguidores", "data", "interacoes", "curtidas",
           "comentarios", "mediana_perfil", "legenda", "link", "coletado"]
COLUNAS_CARROSSEL = COLUNAS + ["capa"]


def chamar(caminho, params=None):
    params = {**(params or {}), "access_token": TOKEN}
    url = f"{API}/{caminho}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace").replace(TOKEN, "***")
        raise RuntimeError(f"{e.code}: {corpo[:240]}") from None


def perfis():
    """[(usuario, grupo)] na ordem do arquivo."""
    lista, grupo = [], ""
    with open(REFERENCIAS, encoding="utf-8") as f:
        for l in f:
            l = l.strip()
            if l.startswith("## "):
                grupo = l[3:].strip()
            elif l and not l.startswith("#"):
                lista.append((l.lstrip("@"), grupo))
    return lista


def posts_de(usuario):
    campos = (f"business_discovery.username({usuario}){{followers_count,"
              f"media.limit({POSTS_POR_PERFIL}){{caption,like_count,comments_count,"
              f"media_product_type,media_type,media_url,timestamp,permalink}}}}")
    bd = chamar(IG_ID, {"fields": campos})["business_discovery"]
    return bd.get("followers_count", 0), bd.get("media", {}).get("data", [])


def main():
    agora = datetime.now(timezone.utc)
    corte = agora - timedelta(days=JANELA_DIAS)
    achados, carrosseis, pulados = [], [], []
    for u, grupo in perfis():
        try:
            seg, posts = posts_de(u)
        except Exception as e:
            pulados.append(f"{u}: {e}")
            continue
        inter = lambda p: p.get("like_count", 0) + p.get("comments_count", 0)
        carrosseis += carrosseis_fora(u, grupo, seg, posts, inter, corte, agora)
        reels = [p for p in posts if p.get("media_product_type") == "REELS" and "like_count" in p]
        if len(reels) < MINIMO_PARA_MEDIANA:
            pulados.append(f"{u}: só {len(reels)} Reels com curtida visível")
            continue
        mediana = statistics.median(inter(p) for p in reels) or 1
        if mediana < MEDIANA_MINIMA and grupo != "gabriel":
            pulados.append(f"{u}: mediana {mediana:.0f} abaixo de {MEDIANA_MINIMA}")
            continue
        regua = VEZES_GRUPO.get(grupo, VEZES)
        for p in reels:
            quando = datetime.fromisoformat(p["timestamp"].replace("+0000", "+00:00"))
            vezes = inter(p) / mediana
            if quando >= corte and vezes >= regua and inter(p) >= MINIMO_INTERACOES:
                achados.append(linha(p, vezes, grupo, u, seg, inter, mediana, agora))
    achados.sort(key=lambda a: (a["grupo"] != "gabriel", -float(a["vezes_acima"])))   # dele primeiro
    gravar(SAIDA, COLUNAS, achados)
    carrosseis.sort(key=lambda a: (a["grupo"] != "gabriel", -float(a["vezes_acima"])))
    gravar(SAIDA_CARROSSEL, COLUNAS_CARROSSEL, carrosseis)
    print(f"{len(achados)} Reels e {len(carrosseis)} carrosséis fora da curva em "
          f"{len(perfis()) - len(pulados)} perfis lidos")
    for p in pulados:
        print("pulado:", p)
    if len(pulados) == len(perfis()):
        sys.exit("nenhum perfil lido: confira a permissão do token para business_discovery")


def linha(p, vezes, grupo, u, seg, inter, mediana, agora):
    quando = datetime.fromisoformat(p["timestamp"].replace("+0000", "+00:00"))
    return {
        "vezes_acima": f"{vezes:.1f}", "grupo": grupo, "perfil": u, "seguidores": seg,
        "data": quando.astimezone(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y"),
        "interacoes": inter(p), "curtidas": p.get("like_count", 0),
        "comentarios": p.get("comments_count", 0), "mediana_perfil": int(mediana),
        "legenda": " ".join((p.get("caption") or "").split())[:220],
        "link": p.get("permalink", ""), "coletado": agora.strftime("%Y-%m-%d %H:%M"),
    }


def carrosseis_fora(u, grupo, seg, posts, inter, corte, agora):
    """Carrossel que venceu a mediana de TODOS os posts do perfil (Reel incluso).

    A régua é mais dura que a do Reel de propósito: carrossel que bate o Reel médio do
    próprio perfil é formato que funciona, não sorte. O perfil pequeno do Gabriel é o caso
    que isso precisa resolver (carrossel com alcance 4 contra Reel com 800).
    """
    validos = [p for p in posts if "like_count" in p]
    if len(validos) < MINIMO_PARA_MEDIANA:
        return []
    mediana = statistics.median(inter(p) for p in validos) or 1
    if mediana < MEDIANA_MINIMA and grupo != "gabriel":
        return []
    saida = []
    for p in validos:
        if p.get("media_type") != "CAROUSEL_ALBUM":
            continue
        quando = datetime.fromisoformat(p["timestamp"].replace("+0000", "+00:00"))
        vezes = inter(p) / mediana
        if quando >= corte and vezes >= VEZES_CARROSSEL and inter(p) >= MINIMO_INTERACOES:
            saida.append({**linha(p, vezes, grupo, u, seg, inter, mediana, agora),
                          "capa": p.get("media_url", "")})
    return saida


def gravar(caminho, colunas, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=colunas)
        w.writeheader()
        w.writerows(linhas)


if __name__ == "__main__":
    main()
