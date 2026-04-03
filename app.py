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
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            return None

        data = response.json()
        if data.get("retcode") != 0:
            return None

        sls_info = data.get("data", {}).get("sls_tracking_info", {})
        order_info = data.get("data", {}).get("order_info", {})
        records = (sls_info.get("records") or []) + (order_info.get("tracking_info") or [])
        
        if not records:
            return None

        records = sorted(records, key=lambda x: x.get("actual_time", 0), reverse=True)
        status_text = records[0].get("description") or records[0].get("seller_description") or "Em trânsito"
        
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

        return {"status": str(status_text), "eventos": eventos}
    except:
        return None

def get_cainiao_tracking(tracking_number):
    """Lógica de rastreamento direta para Cainiao (AliExpress)"""
    url = f"https://global.cainiao.com/global/detail.json?mailNos={tracking_number}&lang=pt-BR"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            module = data.get("module", [])
            if module:
                detail = module[0]
                detail_list = detail.get("detailList", [])
                if detail_list:
                    status_text = detail.get("statusDesc") or "Em trânsito (Cainiao)"
                    eventos = []
                    for item in detail_list:
                        data_str = item.get("timeStr") or item.get("time") or ""
                        descricao = item.get("desc") or ""
                        if data_str and descricao:
                            eventos.append({"data": str(data_str), "descricao": str(descricao)})
                    return {"status": str(status_text), "eventos": eventos}
    except:
        pass
    return None

def get_global_tracking(tracking_number):
    """Lógica de rastreamento global via API do ParcelsApp com limpeza"""
    api_url = "https://parcelsapp.com/api/v2/parcels"
    payload = {"trackingId": tracking_number, "language": "pt", "country": "Brazil"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": "https://parcelsapp.com/en/tracking/",
        "Origin": "https://parcelsapp.com",
        "X-Requested-With": "XMLHttpRequest"
    }

    for attempt in range(2):
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=20)
            if response.status_code == 200:
                data = response.json()
                states = data.get("states", [])
                if states:
                    states = sorted(states, key=lambda x: x.get("date", ""), reverse=True)
                    status_text = states[0].get("status") or "Em trânsito (Global)"
                    eventos = []
                    for state in states:
                        raw_date = state.get("date", "")
                        data_str = raw_date.replace("T", " ").split(".")[0] if "T" in raw_date else raw_date
                        descricao = state.get("status", "")
                        local = state.get("location", "")
                        if local:
                            descricao = f"{descricao} ({local})"
                        
                        if "parcelsapp.com" not in str(descricao).lower():
                            eventos.append({"data": data_str, "descricao": str(descricao)})
                    
                    if eventos:
                        return {"status": str(status_text), "eventos": eventos}
            if attempt == 0:
                time.sleep(5)
        except:
            if attempt == 1: break
            time.sleep(5)

    return {
        "status": "Aguardando atualização",
        "eventos": [
            {"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "descricao": "A transportadora ainda está processando as informações. Tente novamente em alguns instantes."}
        ]
    }

@app.route("/rastreio/<codigo>")
def rastrear_unificado(codigo):
    """ROTA UNIFICADA: Tenta SPX -> Cainiao -> Global"""
    # 1. Tenta SPX
    resultado = get_spx_tracking(codigo)
    if resultado: return jsonify(resultado)
    
    # 2. Tenta Cainiao (para códigos AP, LP, etc.)
    resultado = get_cainiao_tracking(codigo)
    if resultado: return jsonify(resultado)
    
    # 3. Tenta ParcelsApp (Global)
    resultado = get_global_tracking(codigo)
    return jsonify(resultado)

@app.route("/rastreio-global/<codigo>")
def rastrear_global_direto(codigo):
    resultado = get_global_tracking(codigo)
    return jsonify(resultado)

@app.route("/")
def home():
    return "API de rastreamento Sermente V11 (Multi-Provedor) 🚚"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
