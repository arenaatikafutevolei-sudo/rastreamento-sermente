from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import os
import time

app = Flask(__name__)
CORS(app)

def get_spx_tracking(tracking_number):
    """Lógica de rastreamento exclusiva para SPX/Shopee"""
    url = "https://spx.com.br/shipment/order/open/order/get_order_info"
    params = {"spx_tn": tracking_number, "language_code": "pt"}
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
        records = (sls_info.get("records") or []) + (order_info.get("tracking_info") or [])
        records = sorted(records, key=lambda x: x.get("actual_time", 0), reverse=True)

        status_text = records[0].get("description") or records[0].get("seller_description") if records else "Em trânsito"
        eventos = []
        eventos_unicos = set()

        for item in records:
            if item.get("display_flag_v2", 0) > 0 or item.get("display_flag", 0) > 0:
                timestamp = item.get("actual_time")
                data_str = datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %H:%M") if timestamp else ""
                descricao = item.get("seller_description") or item.get("description") or item.get("buyer_description") or "Atualização"
                
                chave = f"{data_str}-{descricao}"
                if chave not in eventos_unicos:
                    eventos_unicos.add(chave)
                    eventos.append({"data": data_str, "descricao": str(descricao)})

        return {"status": status_text, "eventos": eventos}
    except Exception as e:
        return {"erro": True, "mensagem": f"Erro SPX: {str(e)}"}

def get_global_tracking(tracking_number):
    """Lógica de rastreamento global via API do ParcelsApp com Retry"""
    api_url = "https://parcelsapp.com/api/v2/parcels"
    
    payload = {
        "trackingId": tracking_number,
        "language": "pt",
        "country": "Brazil"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": f"https://parcelsapp.com/en/tracking/{tracking_number}",
        "Origin": "https://parcelsapp.com"
    }

    # Lógica de Retry: Tenta até 3 vezes com intervalo de 3 segundos
    # Isso é necessário porque o ParcelsApp inicia a busca em tempo real
    for attempt in range(3):
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=25)
            
            if response.status_code == 200:
                data = response.json()
                states = data.get("states", [])
                
                if states:
                    # Ordena eventos (mais recente primeiro)
                    states = sorted(states, key=lambda x: x.get("date", ""), reverse=True)
                    status_text = states[0].get("status") or "Em trânsito (Global)"
                    eventos = []

                    for state in states:
                        raw_date = state.get("date", "")
                        try:
                            if "T" in raw_date:
                                dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                                data_str = dt.strftime("%d/%m/%Y %H:%M")
                            else:
                                data_str = raw_date
                        except:
                            data_str = raw_date

                        descricao = state.get("status", "")
                        local = state.get("location", "")
                        if local:
                            descricao = f"{descricao} - {local}"

                        eventos.append({"data": data_str, "descricao": descricao})

                    return {"status": status_text, "eventos": eventos}
            
            # Se não encontrou nada, aguarda e tenta novamente
            if attempt < 2:
                time.sleep(3)
                
        except Exception as e:
            if attempt == 2:
                return {"erro": True, "mensagem": f"Erro Global: {str(e)}"}
            time.sleep(3)

    return {"erro": True, "mensagem": "Nenhuma informação encontrada. Tente novamente em alguns instantes, pois a busca global pode demorar."}

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
    return "API de rastreamento Sermente V5 (Python) 🚚"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
