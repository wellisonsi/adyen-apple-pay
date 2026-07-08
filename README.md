# Adyen Apple Pay teste no Render

Esta pasta e um mini-projeto separado para subir no Render Free.

## Antes de subir

Baixe na Adyen/Apple o arquivo de associacao de dominio e coloque aqui com o nome exato:

```text
apple-developer-merchantid-domain-association
```

Sem extensao, sem `.txt`.

## Criar o Git

Dentro desta pasta:

```bash
git init
git add .
git commit -m "Add Render Apple Pay test server"
git branch -M main
git remote add origin URL_DO_SEU_REPO
git push -u origin main
```

## Render

No Render:

1. New > Web Service
2. Conecte o repositorio desta pasta
3. Plano: Free
4. Build Command: `python3 --version`
5. Start Command: `python3 apple-server.py`

Tambem e possivel usar o `render.yaml` deste projeto via Blueprint.

## Variaveis de ambiente

Configure no Render:

```text
LOCAL_HTTPS=false
ADYEN_API_KEY=sua_api_key
ADYEN_CLIENT_KEY=seu_client_key
ADYEN_MERCHANT_ACCOUNT=ENJOEIBR
ADYEN_APPLE_PAY_DOMAIN_NAME=seu-app.onrender.com
PUBLIC_BASE_URL=https://seu-app.onrender.com
```

`ADYEN_APPLE_PAY_DOMAIN_NAME` deve ser apenas o dominio, sem `https://`.

## Validacoes

Depois do deploy, abra:

```text
https://seu-app.onrender.com/health
https://seu-app.onrender.com/config
https://seu-app.onrender.com/.well-known/apple-developer-merchantid-domain-association
https://seu-app.onrender.com/apple.html
```

A URL `.well-known` precisa mostrar o conteudo do arquivo de associacao.

## Adyen

Na Adyen, configure:

```text
Allowed origin:
https://seu-app.onrender.com

Apple Pay domain:
seu-app.onrender.com
```
