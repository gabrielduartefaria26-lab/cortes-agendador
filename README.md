# Agendador de cortes

Publica sozinho no Instagram os 21 cortes, dois por dia, 09:00 e 18:30, de 20/09 a 30/09.
Roda no GitHub Actions. Seu computador pode estar desligado.

## Como funciona

A cada 15 minutos a Action acorda, lê `agenda.json` e verifica se algum item já venceu
sem ter sido publicado. Se venceu, cria o container do Reel na API do Instagram, espera
o processamento terminar e publica. O resultado fica registrado em `estado.json`.

Publica no máximo um por execução. Se dois vencerem juntos por causa de atraso, o segundo
sai no ciclo seguinte.

## Arquivos

| Arquivo | O que é |
|---|---|
| `agenda.json` | Os 21 itens: arquivo, data e hora, legenda |
| `videos/` | Os MP4. Não vão para o Git, vão para o Release |
| `publicar.py` | Conversa com a API do Instagram |
| `estado.json` | O que já foi publicado, com o id de cada post |

## Os três segredos

Em Settings, Secrets and variables, Actions:

| Nome | Valor |
|---|---|
| `IG_TOKEN` | O token do usuário do sistema |
| `IG_USER_ID` | O id da conta do Instagram (número, não o @) |
| `VIDEOS_BASE_URL` | `https://github.com/<usuario>/<repo>/releases/download/videos-v1` |

Cole os valores direto na tela do GitHub. Não passe token por mensagem, e-mail ou arquivo.

## Criar o token, uma vez só

Rota do usuário do sistema. O token não expira e é a mesma estrutura que serve para
publicar na conta de um cliente depois.

**1. Confira os ativos.** Em business.facebook.com, Configurações do Negócio, veja se a
Página `Gabriel D. Faria` e a conta do Instagram estão listadas como ativos do seu Business.
A conta do Instagram precisa ser Profissional e estar vinculada à Página.

**2. Crie o app.** Em developers.facebook.com, Meus apps, Criar app, tipo Empresa.
Vincule o app ao seu Business. Adicione o produto Instagram, opção Instagram Graph API.

**3. Crie o usuário do sistema.** Nas Configurações do Negócio, Usuários, Usuários do
sistema, Adicionar. Nome `agendador`, função Administrador.

**4. Dê os ativos a ele.** No mesmo painel, Adicionar ativos. Marque a Página e a conta
do Instagram, as duas com controle total.

**5. Gere o token.** Botão Gerar novo token, escolha o app do passo 2 e marque:

- `instagram_basic`
- `instagram_content_publish`
- `pages_show_list`
- `pages_read_engagement`
- `business_management`

O token aparece uma vez só. Cole direto no Secret `IG_TOKEN`.

**6. Descubra o id da conta.** Abra no navegador, trocando SEU_TOKEN:

```
https://graph.facebook.com/v21.0/122099024006013574?fields=instagram_business_account&access_token=SEU_TOKEN
```

O número que vier em `instagram_business_account.id` é o `IG_USER_ID`.

## Subir os vídeos

```bash
gh release create videos-v1 videos/*.mp4 --title "Cortes" --notes "Lote 1"
```

O repositório precisa ser público para o Instagram conseguir baixar os arquivos.
Nenhum segredo fica no código: os tokens vivem nos Secrets, que não são expostos.

## Testar antes de confiar

Rode a Action na mão pela aba Actions, botão Run workflow. Se o primeiro item já tiver
vencido, ele publica de verdade. Para um teste seco, adiante a data de um item qualquer
e veja o log.

## Limites

- 50 publicações por conta a cada 24 horas. Você usa 2.
- O vídeo precisa estar em URL pública no momento da publicação.
- A API não agenda nada: quem decide a hora é o cron daqui.
