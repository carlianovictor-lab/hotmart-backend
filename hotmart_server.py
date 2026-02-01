from flask import Flask, request, jsonify
import json
import datetime
import os
import requests

app = Flask(__name__)

# ================= CONFIGURAÇÕES =================
CLIENT_ID = "9134999a-4919-4a96-bc93-60f67c990981"

CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
TOKEN_VALIDACAO = os.getenv("TOKEN_VALIDACAO")

ARQUIVO_VENDAS = "vendas_hotmart.json"
ARQUIVO_TOKEN = "hotmart_token.json"


# ================= UTILIDADES =================
def salvar_venda(venda):
    vendas = []

    if os.path.exists(ARQUIVO_VENDAS):
        with open(ARQUIVO_VENDAS, "r", encoding="utf-8") as f:
            vendas = json.load(f)

    venda["recebido_em"] = datetime.datetime.now().isoformat()
    vendas.append(venda)

    with open(ARQUIVO_VENDAS, "w", encoding="utf-8") as f:
        json.dump(vendas, f, indent=4, ensure_ascii=False)


def salvar_token(token):
    with open(ARQUIVO_TOKEN, "w", encoding="utf-8") as f:
        json.dump(token, f, indent=4, ensure_ascii=False)


def carregar_token():
    if not os.path.exists(ARQUIVO_TOKEN):
        return None

    with open(ARQUIVO_TOKEN, "r", encoding="utf-8") as f:
        return json.load(f)


# ================= OAUTH =================
def trocar_code_por_token(code):
    url = "https://api-sec-vlc.hotmart.com/security/oauth/token"

    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(url, data=payload, headers=headers)

    if response.status_code != 200:
        print("❌ Erro ao trocar code por token:", response.text)
        return None

    return response.json()


# ================= NORMALIZAÇÃO =================
def normalizar_venda(dados):
    try:
        data = dados.get("data", {})

        produto = data.get("product", {}).get("name", "Produto desconhecido")
        comprador = data.get("buyer", {}).get("name", "Cliente")
        valor = (
            data.get("purchase", {})
            .get("price", {})
            .get("value", 0)
        )
        data_compra = (
            data.get("purchase", {})
            .get("approved_date")
        )

        return {
            "produto": produto,
            "valor": float(valor),
            "comprador": comprador,
            "status": dados.get("event"),
            "data": data_compra,
        }

    except Exception as e:
        print("❌ Erro ao normalizar venda:", e)
        return None


# ================= ROTAS =================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Servidor Hotmart ativo"})


@app.route("/hotmart/callback", methods=["GET"])
def hotmart_callback():
    code = request.args.get("code")

    if not code:
        return "❌ Código OAuth não recebido", 400

    token = trocar_code_por_token(code)

    if not token:
        return "❌ Falha ao obter token", 400

    salvar_token(token)
    print("✅ Token OAuth salvo com sucesso")

    return "✅ Hotmart conectada com sucesso! Pode voltar ao app."


@app.route("/hotmart", methods=["POST"])
def hotmart_webhook():
    token = request.headers.get("X-HOTMART-TOKEN")

    if token != TOKEN_VALIDACAO:
        return jsonify({"erro": "Token inválido"}), 401

    dados = request.json

    venda_normalizada = normalizar_venda(dados)

    if not venda_normalizada:
        return jsonify({"erro": "Erro ao processar venda"}), 400

    salvar_venda(venda_normalizada)

    print("✅ Venda normalizada salva:")
    print(json.dumps(venda_normalizada, indent=2, ensure_ascii=False))

    return jsonify({"status": "ok"})


@app.route("/hotmart/vendas", methods=["GET"])
def hotmart_vendas():
    token_data = carregar_token()

    if not token_data:
        return jsonify({"erro": "Hotmart não conectada"}), 401

    access_token = token_data["access_token"]

    url = "https://developers.hotmart.com/payments/api/v1/sales"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return jsonify({
            "erro": "Erro ao buscar vendas",
            "detalhe": response.text
        }), response.status_code

    return jsonify(response.json())


@app.route("/vendas", methods=["GET"])
def listar_vendas():
    if not os.path.exists(ARQUIVO_VENDAS):
        return jsonify([])

    with open(ARQUIVO_VENDAS, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))
