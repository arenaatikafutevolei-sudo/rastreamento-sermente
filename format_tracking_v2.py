import requests
import json
from datetime import datetime

def get_tracking_formatted(tracking_number):
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
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"status": "Erro", "eventos": [{"descricao": f"Erro na consulta: Status {response.status_code}"}]}
        
        data = response.json()
        # Corrigido: retcode em vez de ret_code
        if data.get("retcode") != 0:
            return {"status": "Não encontrado", "eventos": [{"descricao": "Sua busca não gerou resultados"}]}
        
        # Corrigido: sls_tracking_info em vez de order_info
        sls_info = data.get("data", {}).get("sls_tracking_info", {})
        records = sls_info.get("records", [])
        
        # Mapear status principal (baseado no último evento se não houver milestone_code direto)
        status_text = "Em trânsito"
        if records:
            last_event = records[0] # Geralmente o primeiro é o mais recente
            milestone = last_event.get("milestone_code", 2)
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
                dt_object = datetime.fromtimestamp(timestamp)
                data_str = dt_object.strftime("%d/%m/%Y %H:%M")
                
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
        return {"status": "Erro", "eventos": [{"descricao": str(e)}]}

if __name__ == "__main__":
    res = get_tracking_formatted("BR2639864860091")
    print(json.dumps(res, indent=2, ensure_ascii=False))
