from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import os
import time
import json
import re

app = Flask(__name__)
CORS(app)

# Dicionário de tradução expandido
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
    "Out for delivery": "Saiu para entrega ao destinatário",
    "Cleared customs": "Liberação alfandegária concluída",
    "In transit": "Em trânsito",
    "Awaiting collection": "Aguardando retirada",
    "Pick up": "Coletado",
    "Processing": "Em processamento",
    "Departed from local sorting center": "Partiu do centro de triagem local",
    "Arrived at destination hub": "Chegou ao centro de destino",
    "Object in transit": "Objeto em trânsito",
    "Object arrived at sorting center": "Objeto chegou ao centro de triagem",
    "Object departed from sorting center": "Objeto partiu do centro de triagem"
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
        limpo = data_str.replace('T', ' ').split('.')[0].split('+')[0].strip()
        if len(limpo) >= 10:
            if len(limpo) == 10:
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

def get_parcelsapp_tracking(tracking_number):
    """Lógica de rastreamento global via API do ParcelsApp com detecção de novo código"""
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
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            states = data.get("states", [])
            
            # Tenta detectar novo código de rastreio (ex: NN...BR)
            novo_codigo = None
            for attr in data.get("attributes", []):
                if attr.get("name") in ["tracking_number", "destination_tracking_number", "last_tracking_number"]:
                    val = attr.get("val")
                    if val and val != tracking_number and re.match(r'^[A-Z]{2}[0-9]{9}[A-Z]{2}$', val):
                        novo_codigo = val
                        break

            if states:
                states = sorted(states, key=lambda x: x.get("date", ""), reverse=True)
                status_text = states[0].get("status") or "Em trânsito"
                eventos = []
                for state in states:
                    raw_date = state.get("date", "")
                    data_str = raw_date.replace("T", " ").split(".")[0] if "T" in raw_date else raw_date
                    descricao = state.get("status", "")
                    local = state.get("location", "")
                    if local: descricao = f"{descricao} ({local})"
                    if "parcelsapp.com" not in str(descricao).lower():
                        eventos.append({
                            "data": formatar_data_br(data_str),
                            "descricao": traduzir_descricao(str(descricao))
                        })
                return {"status": traduzir_descricao(status_text), "eventos": eventos, "novo_codigo": novo_codigo}
    except:
        pass
    return None

def get_cainiao_tracking_v2(tracking_number):
    """Lógica de rastreamento Cainiao (AliExpress)"""
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
                
                # Tenta detectar novo código de rastreio
                novo_codigo = detail.get("destMailNo") or detail.get("trackingNumber")
                if novo_codigo == tracking_number: novo_codigo = None
                
                eventos = []
                for item in detail_list:
                    raw_date = item.get("timeStr") or item.get("time") or ""
                    raw_desc = item.get("desc") or ""
                    if raw_date and raw_desc:
                        eventos.append({
                            "data": formatar_data_br(str(raw_date)),
                            "descricao": traduzir_descricao(str(raw_desc))
                        })
                if eventos:
                    status_text = detail.get("statusDesc") or eventos[0]["descricao"]
                    return {"status": traduzir_descricao(status_text), "eventos": eventos, "novo_codigo": novo_codigo}
    except:
        pass
    return None

@app.route("/rastreio/<codigo>")
def rastrear_unificado(codigo):
    """ROTA UNIFICADA V23: Prioridade no ParcelsApp para detectar novos códigos"""
    # 1. Tenta SPX primeiro
    resultado_spx = get_spx_tracking(codigo)
    if resultado_spx: return jsonify(resultado_spx)
    
    # 2. Tenta ParcelsApp PRIMEIRO para códigos globais (melhor para detectar NN...BR)
    res_parcels = get_parcelsapp_tracking(codigo)
    res_cainiao = get_cainiao_tracking_v2(codigo)
    
    if not res_cainiao and not res_parcels:
        return jsonify({
            "status": "Aguardando atualização",
            "eventos": [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "descricao": "A transportadora ainda está processando as informações. Tente novamente em alguns instantes."}]
        })
    
    # Mesclagem de eventos
    eventos_finais = []
    chaves_unicas = set()
    todos_eventos = (res_parcels.get("eventos", []) if res_parcels else []) + \
                    (res_cainiao.get("eventos", []) if res_cainiao else [])
    
    # Detecção de novo código (Correios)
    novo_codigo = (res_parcels.get("novo_codigo") if res_parcels else None) or \
                  (res_cainiao.get("novo_codigo") if res_cainiao else None)
    
    # Se detectou um novo código (ex: NN...BR), faz o rastreio em cadeia
    if novo_codigo and re.match(r'^[A-Z]{2}[0-9]{9}[A-Z]{2}$', novo_codigo):
        res_novo = get_parcelsapp_tracking(novo_codigo)
        if res_novo:
            todos_eventos = res_novo.get("eventos", []) + todos_eventos
            status_final = res_novo["status"]
        else:
            status_final = (res_parcels.get("status") if res_parcels else res_cainiao.get("status"))
    else:
        status_final = (res_parcels.get("status") if res_parcels else res_cainiao.get("status"))

    for ev in todos_eventos:
        chave = f"{ev['data'][:16]}-{ev['descricao'][:30]}".lower()
        if chave not in chaves_unicas:
            chaves_unicas.add(chave)
            eventos_finais.append(ev)
    
    try:
        eventos_finais.sort(key=lambda x: datetime.strptime(x['data'], "%d/%m/%Y %H:%M") if len(x['data']) > 10 else datetime.strptime(x['data'], "%d/%m/%Y"), reverse=True)
    except: pass

    return jsonify({"status": status_final, "eventos": eventos_finais})

@app.route("/rastreio-global/<codigo>")
def rastrear_global_direto(codigo):
    resultado = get_parcelsapp_tracking(codigo)
    if not resultado:
        resultado = get_cainiao_tracking_v2(codigo)
    if not resultado:
        return jsonify({"status": "Não encontrado", "eventos": [{"data": "-", "descricao": "Nenhuma informação encontrada."}]})
    return jsonify(resultado)

@app.route("/")
def home():
    return "API de rastreamento Sermente V23 (Deep Link) 🚚"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
