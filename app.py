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

# Dicionário de tradução expandido para cobrir eventos nacionais e internacionais
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
        # Tenta diversos formatos comuns de API
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

def get_correios_tracking(tracking_number):
    """Lógica de rastreamento direta para códigos brasileiros (Correios) via API Linketrack"""
    url = f"https://api.linketrack.com/track/json?user=teste&token=1abcd1234567890&codigo={tracking_number}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            eventos_raw = data.get("eventos", [])
            if eventos_raw:
                eventos = []
                for ev in eventos_raw:
                    data_br = f"{ev.get('data')} {ev.get('hora')}"
                    desc = ev.get("status")
                    local = f"{ev.get('local')} - {ev.get('cidade')}/{ev.get('uf')}"
                    eventos.append({
                        "data": data_br,
                        "descricao": f"{desc} ({local})"
                    })
                return {"status": eventos[0]["descricao"], "eventos": eventos}
    except:
        pass
    return None

def get_cainiao_tracking_v2(tracking_number):
    """Lógica de rastreamento Cainiao com extração forçada de código dos Correios"""
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
            
            # Varredura de texto (Regex Scan) para encontrar códigos brasileiros (ex: NN135003362BR)
            # Focamos em códigos que terminam em BR e começam com duas letras, seguidas de 9 números
            match_br = re.search(r'([A-Z]{2}[0-9]{9}BR)', data_text)
            novo_codigo = match_br.group(1) if match_br else None
            
            # Se o código encontrado for o mesmo que já estamos rastreando, ignoramos como "novo"
            if novo_codigo == tracking_number: novo_codigo = None
            
            module = data.get("module", [])
            if module:
                detail = module[0]
                detail_list = detail.get("detailList", [])
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
    """ROTA UNIFICADA V29: Cainiao + Correios (Sem ParcelsApp)"""
    codigo = str(codigo).strip().upper()
    
    # 1. Tenta SPX primeiro (Prioridade 100%)
    resultado_spx = get_spx_tracking(codigo)
    if resultado_spx: return jsonify(resultado_spx)
    
    # 2. Se for código brasileiro (termina em BR), tenta Correios direto
    if codigo.endswith("BR"):
        resultado_br = get_correios_tracking(codigo)
        if resultado_br: return jsonify(resultado_br)
    
    # 3. Tenta Cainiao (Fonte de Dados Principal para Internacionais)
    res_cainiao = get_cainiao_tracking_v2(codigo)
    
    if not res_cainiao:
        return jsonify({
            "status": "Aguardando atualização",
            "eventos": [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "descricao": "A transportadora ainda está processando as informações. Tente novamente em alguns instantes."}]
        })
    
    # Detecção de novo código (Correios) extraído da Cainiao
    novo_codigo = res_cainiao.get("novo_codigo")
    eventos_finais = res_cainiao.get("eventos", [])
    status_final = res_cainiao.get("status")
    
    # 4. Rastreio em Cadeia: Se detectou um novo código BR, consulta Correios
    if novo_codigo and re.match(r'^[A-Z]{2}[0-9]{9}BR$', novo_codigo):
        res_novo_br = get_correios_tracking(novo_codigo)
        if res_novo_br:
            # Mescla os eventos dos Correios (mais recentes) com os da Cainiao
            eventos_finais = res_novo_br.get("eventos", []) + eventos_finais
            status_final = res_novo_br["status"]

    # Limpeza de duplicados e ordenação
    chaves_unicas = set()
    final = []
    for ev in eventos_finais:
        # Chave baseada em data (minutos) e início da descrição para evitar duplicidade de APIs diferentes
        chave = f"{ev['data'][:16]}-{ev['descricao'][:20]}".lower()
        if chave not in chaves_unicas:
            chaves_unicas.add(chave)
            final.append(ev)
    
    try:
        # Ordena por data decrescente
        final.sort(key=lambda x: datetime.strptime(x['data'], "%d/%m/%Y %H:%M") if len(x['data']) > 10 else datetime.strptime(x['data'], "%d/%m/%Y"), reverse=True)
    except: pass

    return jsonify({"status": status_final, "eventos": final, "novo_codigo": novo_codigo})

@app.route("/")
def home():
    return "API de rastreamento Sermente V29 (Stable Chain) 🚚"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
