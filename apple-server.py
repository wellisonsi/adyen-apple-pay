from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APPLE_PAY_DOMAIN_ASSOCIATION_FILE = "apple-developer-merchantid-domain-association"

ADYEN_API_KEY = os.getenv("ADYEN_API_KEY", "")
ADYEN_CLIENT_KEY = os.getenv("ADYEN_CLIENT_KEY", "")
MERCHANT_ACCOUNT = os.getenv("ADYEN_MERCHANT_ACCOUNT", "ENJOEIBR")

AMOUNT_CURRENCY = os.getenv("ADYEN_AMOUNT_CURRENCY", "BRL")
AMOUNT_VALUE = int(os.getenv("ADYEN_AMOUNT_VALUE", "10000"))
COUNTRY_CODE = os.getenv("ADYEN_COUNTRY_CODE", "BR")
SHOPPER_LOCALE = os.getenv("ADYEN_SHOPPER_LOCALE", "pt-BR")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
APPLE_PAY_DOMAIN_NAME = os.getenv("ADYEN_APPLE_PAY_DOMAIN_NAME", "")

PORT = int(os.getenv("PORT", "3001"))
HTTPS_CERT_FILE = os.getenv("HTTPS_CERT_FILE", "localhost.pem")
HTTPS_KEY_FILE = os.getenv("HTTPS_KEY_FILE", "localhost-key.pem")
LOCAL_HTTPS = os.getenv("LOCAL_HTTPS", "false").lower() not in ("0", "false", "no")


def file_path(file_name):
    return os.path.join(BASE_DIR, file_name)


def json_bytes(payload):
    return json.dumps(payload).encode("utf-8")


def clean_domain_name(value):
    if not value:
        return ""

    parsed = urllib.parse.urlparse(value if "://" in value else f"//{value}")
    domain = parsed.hostname or value
    return domain.strip().lower()


def public_base_url():
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL.rstrip("/")

    scheme = "https" if LOCAL_HTTPS else "http"
    return f"{scheme}://localhost:{PORT}"


class Handler(BaseHTTPRequestHandler):
    def _headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _json(self, status, payload):
        self._headers(status)
        self.wfile.write(json_bytes(payload))

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_HEAD(self):
        if self.path in ("/", "/apple.html"):
            self._headers(200, "text/html")
            return

        if self.path == "/health":
            self._headers(200)
            return

        self._headers(404)

    def do_OPTIONS(self):
        self._headers(200)

    def do_GET(self):
        if self.path in ("/", "/apple.html"):
            self._serve_file("apple.html")
            return

        if self.path == "/return":
            self._serve_file("apple.html")
            return

        if self.path == "/config":
            self._json(200, self._checkout_config())
            return

        if self.path == "/health":
            self._json(200, {"status": "ok"})
            return

        if self.path == "/.well-known/apple-developer-merchantid-domain-association":
            self._serve_domain_association_file()
            return

        self._json(404, {"error": "Not found"})

    def do_POST(self):
        try:
            data = self._read_json()

            if self.path == "/sessions":
                self._create_session(data)
                return

            self._json(404, {"error": "Not found"})

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            print("ERRO ADYEN:")
            print(error_body)

            self._headers(e.code)
            self.wfile.write(error_body.encode("utf-8"))

        except Exception as e:
            print("ERRO BACKEND:")
            print(str(e))
            self._json(500, {"error": str(e)})

    def _serve_file(self, file_name):
        path = file_path(file_name)
        if not os.path.exists(path):
            self._json(404, {"error": f"{file_name} not found"})
            return

        content_type = mimetypes.guess_type(file_name)[0] or "text/plain"
        self._headers(200, content_type)
        with open(path, "rb") as file:
            self.wfile.write(file.read())

    def _serve_domain_association_file(self):
        path = file_path(APPLE_PAY_DOMAIN_ASSOCIATION_FILE)
        if not os.path.exists(path):
            self._json(
                404,
                {
                    "error": f"{APPLE_PAY_DOMAIN_ASSOCIATION_FILE} not found",
                    "hint": "Download the Adyen domain association file and place it in this folder with the exact file name.",
                },
            )
            return

        self._headers(200, "text/plain")
        with open(path, "rb") as file:
            self.wfile.write(file.read())

    def _checkout_config(self):
        return {
            "environment": "test",
            "clientKey": ADYEN_CLIENT_KEY,
            "applePayDomainName": clean_domain_name(APPLE_PAY_DOMAIN_NAME),
            "applePayDomainAssociationFilePresent": os.path.exists(
                file_path(APPLE_PAY_DOMAIN_ASSOCIATION_FILE)
            ),
            "amount": {
                "currency": AMOUNT_CURRENCY,
                "value": AMOUNT_VALUE,
            },
            "countryCode": COUNTRY_CODE,
            "locale": SHOPPER_LOCALE,
        }

    def _create_session(self, data):
        if not ADYEN_API_KEY:
            self._json(
                500,
                {
                    "error": "ADYEN_API_KEY is required.",
                    "hint": "Set ADYEN_API_KEY in Render environment variables.",
                },
            )
            return

        if not ADYEN_CLIENT_KEY:
            self._json(
                500,
                {
                    "error": "ADYEN_CLIENT_KEY is required for Adyen Web Drop-in.",
                    "hint": "Set ADYEN_CLIENT_KEY in Render environment variables.",
                },
            )
            return

        amount = data.get("amount") or {
            "currency": AMOUNT_CURRENCY,
            "value": AMOUNT_VALUE,
        }

        payload = {
            "merchantAccount": MERCHANT_ACCOUNT,
            "amount": amount,
            "reference": data.get("reference", f"APPLEPAY-DROPIN-{int(time.time())}"),
            "returnUrl": data.get("returnUrl") or f"{public_base_url()}/return",
            "countryCode": data.get("countryCode", COUNTRY_CODE),
            "channel": "Web",
            "shopperLocale": data.get("shopperLocale", SHOPPER_LOCALE),
            "allowedPaymentMethods": ["applepay"],
        }

        request = urllib.request.Request(
            "https://checkout-test.adyen.com/v71/sessions",
            data=json_bytes(payload),
            headers={
                "Content-Type": "application/json",
                "X-API-Key": ADYEN_API_KEY,
            },
            method="POST",
        )

        with urllib.request.urlopen(request) as response:
            session = json.loads(response.read().decode("utf-8"))

        print("SESSAO ADYEN:")
        print(json.dumps(session, indent=2))

        self._json(
            200,
            {
                "session": {
                    "id": session["id"],
                    "sessionData": session["sessionData"],
                },
                "config": self._checkout_config(),
                "adyenResponse": session,
            },
        )


def run():
    if LOCAL_HTTPS and (
        not os.path.exists(file_path(HTTPS_CERT_FILE))
        or not os.path.exists(file_path(HTTPS_KEY_FILE))
    ):
        raise SystemExit(
            "Certificado HTTPS local nao encontrado.\n"
            f"Crie {HTTPS_CERT_FILE} e {HTTPS_KEY_FILE} ou configure HTTPS_CERT_FILE/HTTPS_KEY_FILE."
        )

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)

    scheme = "http"
    if LOCAL_HTTPS:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(file_path(HTTPS_CERT_FILE), file_path(HTTPS_KEY_FILE))
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"

    print(f"Apple Pay Adyen Drop-in server: {scheme}://0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
