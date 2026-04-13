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

# Dicionário de tradução para eventos internacionais e nacionais
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
    "Cleared customs": "Liberação alfandegária concluída",
    "In transit": "Em trânsito",
    "Awaiting collection": "Aguardando retirada",
    "Pick up": "Coletado",
    "Processing": "Em processamento",
    "Departed from local sorting center": "Partiu do centro de triagem local",
    "Arrived at destination hub": "Chegou ao centro de destino",
    "Object in transit": "Objeto em trânsito",
    "Object arrived at sorting center": "Objeto chegou ao centro de triagem",
    "Object departed from sorting center": "Objeto partiu do centro de triagem",
    "Posted": "Postado",
    "Forwarded": "Encaminhado",
    "Arrived at unit": "Chegou na unidade",
    "Departed from unit": "Saiu da unidade"
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
        # Lida com formatos de data brasileiros curtos (ex: 10 abr)
        meses = {"jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05", "jun": "06", 
                 "jul": "07", "ago": "08", "set": "09", "out": "10", "nov": "11", "dez": "12"}
        match_curto = re.search(r'(\d+)\s+([a-z]{3})', data_str.lower())
        if match_curto:
            dia = match_curto.group(1).zfill(2)
            mes = meses.get(match_curto.group(2), "01")
            ano = datetime.now().year
            return f"{dia}/{mes}/{ano}"

        if data_str.isdigit() and len(data_str) >= 13:
            dt = datetime.fromtimestamp(int(data_str) / 1000)
            return dt.strftime("%d/%m/%Y %H:%M")
        
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

def get_correios_tracking(tracking_number):
    url = f"https://api.linketrack.com/track/json?user=teste&token=1abcd1234567890&codigo={tracking_number}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            eventos_raw = data.get("eventos", [])
            if eventos_raw:
                eventos = []
                for ev in eventos_raw:
                    data_br = f"{ev.get('data')} {ev.get('hora')}"
                    desc = ev.get("status")
                    local = f"{ev.get('local')} - {ev.get('cidade')}/{ev.get('uf')}"
                    eventos.append({"data": data_br, "descricao": f"{desc} ({local})"})
                return {"status": eventos[0]["descricao"], "eventos": eventos}
    except: pass
    return None

def get_cainiao_tracking_v2(tracking_number):
    url = f"https://global.cainiao.com/global/detail.json?mailNos={tracking_number}&lang=pt-BR"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://global.cainiao.com/"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data_text = response.text
            data = response.json()
            match_br = re.search(r'([A-Z]{2}[0-9]{9}BR)', data_text)
            novo_codigo = match_br.group(1) if match_br else None
            if novo_codigo == tracking_number: novo_codigo = None
            module = data.get("module", [])
            if module:
                detail = module[0]
                detail_list = detail.get("detailList", [])
                eventos = []
                for item in detail_list:
                    raw_date = item.get("timeStr") or item.get("time") or ""
                    raw_desc = item.get("standerdDesc") or item.get("desc") or item.get("descTitle") or ""
                    if raw_date and raw_desc:
                        eventos.append({
                            "data": formatar_data_br(str(raw_date)),
                            "descricao": traduzir_descricao(str(raw_desc))
                        })
                if not eventos and detail.get("latestEvent"):
                    eventos.append({
                        "data": formatar_data_br(detail.get("latestEventTimeStr")),
                        "descricao": traduzir_descricao(detail.get("latestEventDesc"))
                    })
                if eventos or novo_codigo:
                    status_text = detail.get("statusDesc") or (eventos[0]["descricao"] if eventos else "Em trânsito")
                    return {"status": traduzir_descricao(status_text), "eventos": eventos, "novo_codigo": novo_codigo}
    except: pass
    return None

def get_loggi_tracking(tracking_code):
    """
    Lógica de rastreamento para Loggi melhorada (V45).
    Tenta primeiro a API pública da Loggi com headers de navegador mobile.
    Se falhar, tenta o Linketrack.
    """
    tracking_code = str(tracking_code).strip().upper()
    
    # 1. Tentativa via API Pública da Loggi (Headers Mobile para evitar Cloudflare)
    try:
        url_api = f"https://www.loggi.com/rastreador/api/v1/packages/{tracking_code}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"https://www.loggi.com/rastreador/{tracking_code}",
            "X-Requested-With": "XMLHttpRequest",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        res_api = requests.get(url_api, headers=headers, timeout=12)
        
        if res_api.status_code == 200:
            data = res_api.json()
            status_raw = data.get("status", "Em trânsito")
            
            # Mapeamento de status amigáveis
            status_map = {
                "CHECKED_IN": "Preparando para transferência",
                "OUT_FOR_DELIVERY": "Saiu para entrega",
                "DELIVERED": "Entregue",
                "STOCKED": "Recebido na unidade",
                "PICKED_UP": "Coletado",
                "PENDING": "Pedido criado",
                "CANCELED": "Cancelado"
            }
            status = status_map.get(status_raw, status_raw)
            
            history = data.get("tracking_history", [])
            eventos = []
            for h in history:
                data_evento = formatar_data_br(h.get("date"))
                desc = h.get("status_text") or h.get("status")
                if data_evento and desc:
                    eventos.append({"data": data_evento, "descricao": str(desc)})
            
            # Ordenar eventos por data decrescente
            if eventos:
                try:
                    eventos.sort(key=lambda x: datetime.strptime(x['data'], "%d/%m/%Y %H:%M") if len(x['data']) > 10 else datetime.strptime(x['data'], "%d/%m/%Y"), reverse=True)
                except: pass
            else:
                eventos.append({
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "descricao": status
                })
            
            return {"status": status, "eventos": eventos}
    except: pass

    # 2. Fallback: Linketrack (Proxy)
    try:
        url_link = f"https://api.linketrack.com/track/json?user=teste&token=1abcd1234567890&codigo={tracking_code}"
        res_link = requests.get(url_link, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if res_link.status_code == 200:
            data = res_link.json()
            eventos_raw = data.get("eventos", [])
            if eventos_raw:
                eventos = []
                for ev in eventos_raw:
                    data_br = f"{ev.get('data')} {ev.get('hora')}"
                    desc = ev.get("status")
                    local = f"{ev.get('local', '')} {ev.get('cidade', '')}/{ev.get('uf', '')}".strip()
                    eventos.append({"data": data_br, "descricao": f"{desc} ({local})" if local else desc})
                return {"status": eventos[0]["descricao"], "eventos": eventos}
    except: pass
    
    return None

def logic_unificada(codigo):
    codigo = str(codigo).strip().upper()
    
    # 1. SPX (Prioridade Máxima)
    res_spx = get_spx_tracking(codigo)
    if res_spx: return res_spx

    # 2. Loggi (Identificação por Padrão)
    # Padrões: NE...LG, MR..., ou códigos que terminam em LG
    if codigo.startswith("NE") or codigo.startswith("MR") or codigo.endswith("LG"):
        res_loggi = get_loggi_tracking(codigo)
        if res_loggi: return res_loggi
    
    # 3. Correios Direto
    if codigo.endswith("BR") and len(codigo) == 13:
        res_br = get_correios_tracking(codigo)
        if res_br: return res_br
    
    # 4. Cainiao (Internacional)
    res_cainiao = get_cainiao_tracking_v2(codigo)
    if res_cainiao:
        novo_codigo = res_cainiao.get("novo_codigo")
        eventos_finais = res_cainiao.get("eventos", [])
        status_final = res_cainiao.get("status")
        
        # 5. Chain Tracking (Cainiao -> Correios)
        if novo_codigo and re.match(r'^[A-Z]{2}[0-9]{9}BR$', novo_codigo):
            res_novo_br = get_correios_tracking(novo_codigo)
            if res_novo_br:
                eventos_finais = res_novo_br.get("eventos", []) + eventos_finais
                status_final = res_novo_br["status"]

        # Limpeza e Ordenação
        chaves_unicas = set()
        final = []
        for ev in eventos_finais:
            desc_limpa = re.sub(r'[^\w\s]', '', ev['descricao'][:30]).strip().lower()
            chave = f"{ev['data'][:16]}-{desc_limpa}"
            if chave not in chaves_unicas:
                chaves_unicas.add(chave)
                final.append(ev)
        
        try:
            final.sort(key=lambda x: datetime.strptime(x['data'], "%d/%m/%Y %H:%M") if len(x['data']) > 10 else datetime.strptime(x['data'], "%d/%m/%Y"), reverse=True)
        except: pass

        return {"status": status_final, "eventos": final, "codigo_original": codigo, "novo_codigo": novo_codigo}

    # Fallback Final para Loggi (Caso não tenha batido no padrão inicial)
    res_loggi_final = get_loggi_tracking(codigo)
    if res_loggi_final: return res_loggi_final

    return {
        "status": "Aguardando atualização",
        "eventos": [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "descricao": "A transportadora ainda está processando as informações."}],
        "codigo_original": codigo
    }

@app.route("/rastreio/<codigo>")
def rastrear(codigo):
    return jsonify(logic_unificada(codigo))

@app.route("/rastreio-global/<codigo>")
def rastrear_global(codigo):
    return jsonify(logic_unificada(codigo))

@app.route("/")
def home():
    return "API de rastreamento Sermente V45 (Loggi Fixed) 🚚"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
