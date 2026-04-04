from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import os
import time
import re
import json

app = Flask(__name__)
CORS(app)

# Dicionário de tradução para termos comuns da Cainiao/AliExpress/ParcelsApp
TRADUCOES = {
    "Leave the warehouse": "Saiu do armazém",
    "Package finished": "Pacote processado e finalizado",
    "Order received successfully": "Pedido recebido com sucesso",
    "Arrived at departure transport hub": "Chegou ao centro de transporte de partida",
    "Outbound in sorting center": "Saindo do centro de triagem",
    "Inbound in sorting center": "Chegou ao centro de triagem",
    "Accepted by carrier": "Aceito pela transportadora",
    "Waiting for pickup": "Aguardando coleta",
    "Shipped by air": "Enviado por transporte aéreo",
    "Arrived at destination country": "Chegou ao país de destino",
    "Customs clearance started": "Iniciado o desembaraço aduaneiro",
    "Customs clearance successful": "Desembaraço aduaneiro concluído com sucesso",
    "Held by customs": "Retido pela alfândega",
    "Delivered": "Entregue",
    "Out for delivery": "Saiu para entrega",
    "Arrived at local delivery center": "Chegou ao centro de distribuição local",
    "Departed from sorting center": "Partiu do centro de triagem",
    "Arrived at sorting center": "Chegou ao centro de triagem",
    "Hand over to airline": "Entregue à companhia aérea",
    "Departed from departure country": "Partiu do país de origem",
    "Arrived at destination country/region": "Chegou ao país/região de destino",
    "Import customs clearance complete": "Desembaraço aduaneiro de importação concluído",
    "Import customs clearance started": "Desembaraço aduaneiro de importação iniciado",
    "Received by local delivery company": "Recebido pela empresa de entrega local",
    "Arrived at local sorting center": "Chegou ao centro de triagem local",
    "Out for delivery": "Saiu para entrega ao destinatário"
}

def traduzir_descricao(texto):
    if not texto: return "Atualização"
    texto_str = str(texto)
    for termo_en, termo_pt in TRADUCOES.items():
        if termo_en.lower() in texto_str.lower():
            return termo_pt
    return texto_str

def formatar_data_br(data_str):
    if not data_str: return "-"
    data_str = str(data_str)
    try:
        # Tenta converter de ISO (2026-04-01T22:33:00Z) para BR (01/04/2026 22:33)
        limpo = data_str.replace('T', ' ').split('.')[0].split('+')[0].strip()
        if len(limpo) >= 10:
            if len(limpo) == 10: # Apenas data YYYY-MM-DD
                dt = datetime.strptime(limpo, "%Y-%m-%d")
                return dt.strftime("%d/%m/%Y")
            dt = datetime.strptime(limpo[:19], "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d/%m/%Y %H:%M")
        return data_str
    except:
        return data_str

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
        if response.status_code != 200: return None
        data = response.json()
        if data.get("retcode") != 0: return None
        sls_info = data.get("data", {}).get("sls_tracking_info", {})
        order_info = data.get("data", {}).get("order_info", {})
        records = (sls_info.get("records") or []) + (order_info.get("tracking_info") or [])
        if not records: return None
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
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://global.cainiao.com/"
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
                    status_text = detail.get("statusDesc") or "Em trânsito"
                    eventos = []
                    for item in detail_list:
                        raw_date = item.get("timeStr") or item.get("time") or ""
                        raw_desc = item.get("desc") or ""
                        if raw_date and raw_desc:
                            eventos.append({
                                "data": formatar_data_br(str(raw_date)),
                                "descricao": traduzir_descricao(str(raw_desc))
                            })
                    return {"status": traduzir_descricao(status_text), "eventos": eventos}
    except:
        pass
    return None

def get_parcelsapp_scraping(tracking_number):
    """Lógica de rastreamento global via Scraping de HTML do ParcelsApp (Mais resistente a bloqueios)"""
    url = f"https://parcelsapp.com/pt/tracking/{tracking_number}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        html = response.text
        
        # O ParcelsApp injeta os dados de rastreio em um script JS na página
        # Procuramos pelo padrão: window.parcel = {...}
        match = re.search(r'window\.parcel\s*=\s*({.*?});', html, re.DOTALL)
        
        if match:
            parcel_data = json.loads(match.group(1))
            states = parcel_data.get("states", [])
            
            if states:
                states = sorted(states, key=lambda x: x.get("date", ""), reverse=True)
                status_text = states[0].get("status") or "Em trânsito"
                eventos = []
                for state in states:
                    raw_date = state.get("date", "")
                    descricao = state.get("status", "")
                    local = state.get("location", "")
                    if local: descricao = f"{descricao} ({local})"
                    if "parcelsapp.com" not in str(descricao).lower():
                        eventos.append({
                            "data": formatar_data_br(raw_date),
                            "descricao": traduzir_descricao(str(descricao))
                        })
                return {"status": traduzir_descricao(status_text), "eventos": eventos}
    except Exception as e:
        print(f"Erro no scraping: {e}")
    return None

@app.route("/rastreio/<codigo>")
def rastrear_unificado(codigo):
    """ROTA UNIFICADA: Tenta SPX -> Mescla Cainiao + ParcelsApp (Scraping)"""
    # 1. Tenta SPX primeiro
    resultado_spx = get_spx_tracking(codigo)
    if resultado_spx: return jsonify(resultado_spx)
    
    # 2. Mescla Cainiao e ParcelsApp (Scraping)
    res_cainiao = get_cainiao_tracking(codigo)
    res_parcels = get_parcelsapp_scraping(codigo)
    
    if not res_cainiao and not res_parcels:
        return jsonify({
            "status": "Aguardando atualização",
            "eventos": [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "descricao": "A transportadora ainda está processando as informações. Tente novamente em alguns instantes."}]
        })
    
    eventos_finais = []
    chaves_unicas = set()
    todos_eventos = (res_cainiao.get("eventos", []) if res_cainiao else []) + \
                    (res_parcels.get("eventos", []) if res_parcels else [])
    
    for ev in todos_eventos:
        # Chave para evitar duplicados
        chave = f"{ev['data'][:16]}-{ev['descricao'][:30]}".lower()
        if chave not in chaves_unicas:
            chaves_unicas.add(chave)
            eventos_finais.append(ev)
    
    # Ordena por data (mais recente primeiro)
    try:
        eventos_finais.sort(key=lambda x: datetime.strptime(x['data'], "%d/%m/%Y %H:%M") if len(x['data']) > 10 else datetime.strptime(x['data'], "%d/%m/%Y"), reverse=True)
    except:
        pass

    status_final = "Em trânsito"
    if res_parcels and res_parcels.get("status"):
        status_final = res_parcels["status"]
    elif res_cainiao and res_cainiao.get("status"):
        status_final = res_cainiao["status"]

    return jsonify({"status": status_final, "eventos": eventos_finais})

@app.route("/rastreio-global/<codigo>")
def rastrear_global_direto(codigo):
    """Rota direta para o ParcelsApp (Scraping)"""
    resultado = get_parcelsapp_scraping(codigo)
    if not resultado:
        resultado = get_cainiao_tracking(codigo)
    
    if not resultado:
        return jsonify({
            "status": "Não encontrado",
            "eventos": [{"data": "-", "descricao": "Nenhuma informação encontrada para este código global."}]
        })
    return jsonify(resultado)

@app.route("/")
def home():
    return "API de rastreamento Sermente V18 (Scraping) 🚚"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
