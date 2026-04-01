from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import os
import re

app = Flask(__name__)
CORS(app)

def get_spx_tracking(tracking_number):
    """Lógica de rastreamento exclusiva para SPX/Shopee"""
    url = "https://spx.com.br/shipment/order/open/order/get_order_info"
    params = {
        "spx_tn": tracking_number,
        "language_code": "pt"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://spx.com.br/track?{tracking_number}",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code != 200:
            return {"erro": True, "mensagem": f"Erro na consulta SPX: {response.status_code}"}

        data = response.json()
        if data.get("retcode") != 0:
            return {"erro": True, "mensagem": "Código SPX não encontrado"}

        sls_info = data.get("data", {}).get("sls_tracking_info", {})
        order_info = data.get("data", {}).get("order_info", {})
        
        # Unifica registros de eventos
        records = (sls_info.get("records") or []) + (order_info.get("tracking_info") or [])
        
        # Ordenar do mais recente
        records = sorted(records, key=lambda x: x.get("actual_time", 0), reverse=True)

        status_text = "Em trânsito"
        if records:
            status_text = records[0].get("description") or records[0].get("seller_description") or "Em trânsito"

        eventos = []
        eventos_unicos = set()

        for item in records:
            # Verifica flags de visibilidade da SPX
            if item.get("display_flag_v2", 0) > 0 or item.get("display_flag", 0) > 0:
                timestamp = item.get("actual_time")
                data_str = datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %H:%M") if timestamp else ""
                
                descricao = item.get("seller_description") or item.get("description") or item.get("buyer_description") or "Atualização"
                descricao = str(descricao)

                chave = f"{data_str}-{descricao}"
                if chave not in eventos_unicos:
                    eventos_unicos.add(chave)
                    eventos.append({"data": data_str, "descricao": descricao})

        return {"status": status_text, "eventos": eventos}
    except Exception as e:
        return {"erro": True, "mensagem": f"Erro SPX: {str(e)}"}

def get_global_tracking(tracking_number):
    """Lógica de rastreamento global via ParcelsApp (Simulação)"""
    url = f"https://parcelsapp.com/en/tracking/{tracking_number}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try:
        # Nota: O ParcelsApp é um site dinâmico. Esta rota fornece o link direto e 
        # tenta capturar o status básico se disponível no HTML inicial.
        response = requests.get(url, headers=headers, timeout=15)
        
        if "No information about your package" in response.text:
            return {"erro": True, "mensagem": "Código não encontrado no ParcelsApp"}

        # Formato compatível com a index
        return {
            "status": "Em trânsito (Global)",
            "eventos": [
                {
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "descricao": "Consulta realizada via ParcelsApp. Clique no link abaixo para detalhes completos."
                },
                {
                    "data": "-",
                    "descricao": f"Link Direto: https://parcelsapp.com/en/tracking/{tracking_number}"
                }
            ]
        }
    except Exception as e:
        return {"erro": True, "mensagem": f"Erro Global: {str(e)}"}

@app.route("/rastreio/<codigo>")
def rastrear_spx(codigo):
    resultado = get_spx_tracking(codigo)
    return jsonify(resultado)

@app.route("/rastreio-global/<codigo>")
def rastrear_global(codigo):
    resultado = get_global_tracking(codigo)
    return jsonify(resultado)

@app.route("/")
def home():
    return "API de rastreamento Sermente V3 (Python) 🚚"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
