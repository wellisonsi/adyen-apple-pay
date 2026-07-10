# Adyen Apple Pay API-only teste no Render

Esta pasta e um mini-projeto separado para subir no Render Free usando Apple Pay API-only.

Neste fluxo nao usamos Adyen Drop-in nem `/sessions`.

O fluxo e:

```text
1. Front chama /paymentMethods no seu backend.
2. Backend chama /paymentMethods na Adyen.
3. Front monta o botao Apple Pay e abre ApplePaySession.
4. Front recebe onvalidatemerchant.
5. Backend chama /applePay/sessions na Adyen.
6. Front chama completeMerchantValidation.
7. Shopper autoriza no Apple Pay.
8. Front envia applePayToken para /payments no seu backend.
9. Backend chama /payments na Adyen.
```

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

O `render.yaml` ja define estas variaveis com valores padrao:

```text
LOCAL_HTTPS=false
ADYEN_MERCHANT_ACCOUNT=ENJOEIBR
ADYEN_AMOUNT_CURRENCY=BRL
ADYEN_AMOUNT_VALUE=10000
ADYEN_COUNTRY_CODE=BR
ADYEN_SHOPPER_LOCALE=pt-BR
```

Estas voce precisa preencher manualmente no Render, porque sao segredo ou dependem da URL criada:

```text
ADYEN_API_KEY=sua_api_key
ADYEN_APPLE_PAY_DOMAIN_NAME=seu-app.onrender.com
PUBLIC_BASE_URL=https://seu-app.onrender.com
```

`ADYEN_APPLE_PAY_DOMAIN_NAME` deve ser apenas o dominio, sem `https://`.

`PUBLIC_BASE_URL` deve ser a URL completa, com `https://`.

No `render.yaml`, `sync: false` significa: "o Render vai pedir para voce informar esse valor no painel e nao vai salvar o segredo no Git".

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
Apple Pay Shop website:
https://seu-app.onrender.com
```

Para API-only puro nao usamos o `ADYEN_CLIENT_KEY` no navegador, entao Allowed origins deixa de ser o ponto principal deste teste. O importante e o Apple Pay estar habilitado para o merchant account e o dominio estar configurado como shop website/domínio Apple Pay.
