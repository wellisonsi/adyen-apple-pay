from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import json
import mimetypes
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APPLE_PAY_DOMAIN_ASSOCIATION_FILE = "apple-developer-merchantid-domain-association"

ADYEN_API_KEY = os.getenv("ADYEN_API_KEY", "")
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

            if self.path == "/paymentMethods":
                self._payment_methods(data)
                return

            if self.path == "/apple-pay-session":
                self._apple_pay_session(data)
                return

            if self.path == "/payments":
                self._payments(data)
                return

            self._json(404, {"error": "Not found"})

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

    def _adyen_request(self, version, path, payload, idempotency_key=None):
        if not ADYEN_API_KEY:
            raise RuntimeError("ADYEN_API_KEY is required.")

        url = f"https://checkout-test.adyen.com/{version}{path}"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": ADYEN_API_KEY,
        }
        debug_headers = {
            "Content-Type": "application/json",
            "X-API-Key": "[REDACTED]",
        }

        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
            debug_headers["Idempotency-Key"] = idempotency_key

        request = urllib.request.Request(
            url,
            data=json_bytes(payload),
            headers=headers,
            method="POST",
        )

        debug = {
            "request": {
                "method": "POST",
                "url": url,
                "headers": debug_headers,
                "body": payload,
            }
        }

        try:
            with urllib.request.urlopen(request) as response:
                response_body = response.read().decode("utf-8")
                response_payload = json.loads(response_body) if response_body else {}
                debug["response"] = {
                    "status": response.status,
                    "headers": dict(response.headers.items()),
                    "body": response_payload,
                }
                return response_payload, debug
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_payload = json.loads(error_body) if error_body else {}
            except json.JSONDecodeError:
                error_payload = {"rawBody": error_body}

            debug["response"] = {
                "status": e.code,
                "headers": dict(e.headers.items()),
                "body": error_payload,
            }

            print("ERRO ADYEN:")
            print(json.dumps(debug, indent=2))

            self._json(e.code, {"adyenError": error_payload, "debug": debug})
            return None, debug

    def _payment_methods(self, data):
        payload = {
            "merchantAccount": MERCHANT_ACCOUNT,
            "amount": data.get("amount")
            or {
                "currency": AMOUNT_CURRENCY,
                "value": AMOUNT_VALUE,
            },
            "countryCode": data.get("countryCode", COUNTRY_CODE),
            "channel": "Web",
        }

        payment_methods, debug = self._adyen_request("v72", "/paymentMethods", payload)
        if payment_methods is None:
            return

        self._json(
            200,
            {
                "config": self._checkout_config(),
                "adyenResponse": payment_methods,
                "debug": debug,
            },
        )

    def _apple_pay_session(self, data):
        payload = {
            "displayName": data["displayName"],
            "domainName": data.get("domainName")
            or clean_domain_name(APPLE_PAY_DOMAIN_NAME),
            "merchantIdentifier": data["merchantIdentifier"],
        }

        adyen_response, debug = self._adyen_request("v64", "/applePay/sessions", payload)
        if adyen_response is None:
            return

        decoded_session = json.loads(
            base64.b64decode(adyen_response["data"]).decode("utf-8")
        )

        self._json(
            200,
            {
                "applePaySession": decoded_session,
                "config": self._checkout_config(),
                "adyenResponse": adyen_response,
                "debug": debug,
            },
        )

    def _payments(self, data):
        amount = data.get("amount") or {
            "currency": AMOUNT_CURRENCY,
            "value": AMOUNT_VALUE,
        }

        payload = {
            "merchantAccount": MERCHANT_ACCOUNT,
            "reference": data.get("reference", f"APPLEPAY-API-{int(time.time())}"),
            "amount": amount,
            "paymentMethod": {
                "type": "applepay",
                "applePayToken": data["applePayToken"],
            },
            "storePaymentMethod": true,
            "recurringProcessingModel": "Subscription",
            "returnUrl": data.get("returnUrl") or f"{public_base_url()}/return",
        }

        payment, debug = self._adyen_request(
            "v72",
            "/payments",
            payload,
            idempotency_key=data.get("idempotencyKey") or str(uuid.uuid4()),
        )
        if payment is None:
            return

        self._json(
            200,
            {
                "payment": payment,
                "config": self._checkout_config(),
                "debug": debug,
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

    print(f"Apple Pay API-only server: {scheme}://0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
