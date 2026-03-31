from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

def get_tracking_formatted(tracking_number):
    url = "https://spx.com.br/shipment/order/open/order/get_order_info"
    
    params = {
        "spx_tn": tracking_number,
        "language_code": "pt"
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://spx.com.br/track?{tracking_number}",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code != 200:
            return {"erro": True, "mensagem": f"Erro na consulta: {response.status_code}"}

        data = response.json()

        if data.get("retcode") != 0:
            return {"erro": True, "mensagem": "Código não encontrado"}

        sls_info = data.get("data", {}).get("sls_tracking_info", {})
        records = sls_info.get("records", [])

        status_text = "Em trânsito"

        if records:
            milestone = records[0].get("milestone_code", 2)

            status_map = {
                1: "Em preparação",
                2: "Em trânsito",
                3: "Em trânsito",
                4: "Saiu para entrega",
                5: "Entregue"
            }

            status_text = status_map.get(milestone, "Em trânsito")

        eventos = []

        for item in records:
            if item.get("display_flag_v2", 0) > 0:
                timestamp = item.get("actual_time")

                if timestamp:
                    dt_object = datetime.fromtimestamp(timestamp)
                    data_str = dt_object.strftime("%d/%m/%Y %H:%M")
                else:
                    data_str = ""

                descricao = item.get("description") or item.get("seller_description")

                eventos.append({
                    "data": data_str,
                    "descricao": descricao
                })

        return {
            "status": status_text,
            "eventos": eventos
        }

    except Exception as e:
        return {"erro": True, "mensagem": str(e)}


@app.route("/rastreio/<codigo>")
def rastrear(codigo):
    resultado = get_tracking_formatted(codigo)
    return jsonify(resultado)


@app.route("/")
def home():
    return "API de rastreamento funcionando 🚚"


if __name__ == "__main__":
    import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)