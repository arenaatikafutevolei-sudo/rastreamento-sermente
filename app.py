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
    """Lógica de rastreamento direta para códigos brasileiros (Correios)"""
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
    """Lógica de rastreamento Cainiao com varredura de texto para novo código"""
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
            # Procuramos por qualquer padrão de 2 letras + 9 números + BR
            match_br = re.search(r'[A-Z]{2}[0-9]{9}BR', data_text)
            novo_codigo = match_br.group(0) if match_br else None
            if novo_codigo == tracking_number: novo_codigo = None
            
            module = data.get("module", [])
            if module:
                detail = module[0]
                detail_list = detail.get("detailList", [])
                milestones = detail.get("milestoneList", [])
                
                eventos = []
                chaves = set()
                for item in detail_list:
                    raw_date = item.get("timeStr") or item.get("time") or ""
                    raw_desc = item.get("desc") or ""
                    if raw_date and raw_desc:
                        data_br = formatar_data_br(str(raw_date))
                        desc_br = traduzir_descricao(str(raw_desc))
                        chave = f"{data_br}-{desc_br}"
                        if chave not in chaves:
                            chaves.add(chave)
                            eventos.append({"data": data_br, "descricao": desc_br})
                
                for ms in milestones:
                    raw_date = ms.get("timeStr") or ms.get("time") or ""
                    raw_desc = ms.get("desc") or ms.get("statusDesc") or ""
                    if raw_date and raw_desc:
                        data_br = formatar_data_br(str(raw_date))
                        desc_br = traduzir_descricao(str(raw_desc))
                        chave = f"{data_br}-{desc_br}"
                        if chave not in chaves:
                            chaves.add(chave)
                            eventos.append({"data": data_br, "descricao": desc_br})
                
                if eventos:
                    eventos.sort(key=lambda x: datetime.strptime(x['data'], "%d/%m/%Y %H:%M") if len(x['data']) > 10 else datetime.strptime(x['data'], "%d/%m/%Y"), reverse=True)
                    status_text = detail.get("statusDesc") or eventos[0]["descricao"]
                    return {"status": traduzir_descricao(status_text), "eventos": eventos, "novo_codigo": novo_codigo}
    except:
        pass
    return None

@app.route("/rastreio/<codigo>")
def rastrear_unificado(codigo):
    """ROTA UNIFICADA V26: Tenta SPX -> Correios (se BR) -> Cainiao V2 (com Regex Scan)"""
    # 1. Tenta SPX primeiro
    resultado = get_spx_tracking(codigo)
    if resultado: return jsonify(resultado)
    
    # 2. Se for código brasileiro (termina em BR), tenta Correios direto
    if str(codigo).upper().endswith("BR"):
        resultado_br = get_correios_tracking(codigo)
        if resultado_br: return jsonify(resultado_br)
    
    # 3. Tenta Cainiao com varredura de texto para novo código
    resultado_cainiao = get_cainiao_tracking_v2(codigo)
    if resultado_cainiao:
        novo_codigo = resultado_cainiao.get("novo_codigo")
        # Se detectou um novo código BR no meio do texto da Cainiao, rastreia ele também!
        if novo_codigo and str(novo_codigo).upper().endswith("BR"):
            resultado_br = get_correios_tracking(novo_codigo)
            if resultado_br:
                # Mescla os eventos da Cainiao com os dos Correios
                eventos_finais = resultado_br["eventos"] + resultado_cainiao["eventos"]
                chaves = set()
                final = []
                for ev in eventos_finais:
                    chave = f"{ev['data'][:16]}-{ev['descricao'][:30]}".lower()
                    if chave not in chaves:
                        chaves.add(chave)
                        final.append(ev)
                try:
                    final.sort(key=lambda x: datetime.strptime(x['data'], "%d/%m/%Y %H:%M") if len(x['data']) > 10 else datetime.strptime(x['data'], "%d/%m/%Y"), reverse=True)
                except: pass
                return jsonify({"status": resultado_br["status"], "eventos": final, "novo_codigo": novo_codigo})
        
        return jsonify(resultado_cainiao)
    
    # 4. Resposta padrão se nada for encontrado
    return jsonify({
        "status": "Aguardando atualização",
        "eventos": [{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "descricao": "A transportadora ainda está processando as informações. Tente novamente em alguns instantes."}]
    })

@app.route("/rastreio-global/<codigo>")
def rastrear_global_direto(codigo):
    if str(codigo).upper().endswith("BR"):
        resultado = get_correios_tracking(codigo)
        if resultado: return jsonify(resultado)
    
    resultado = get_cainiao_tracking_v2(codigo)
    if not resultado:
        return jsonify({"status": "Não encontrado", "eventos": [{"data": "-", "descricao": "Nenhuma informação encontrada."}]})
    return jsonify(resultado)

@app.route("/")
def home():
    return "API de rastreamento Sermente V26 (Regex Scan) 🚚"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
