/**
 * Servidor de Rastreamento Sermente (VERSÃO CORRIGIDA - API SPX 2026)
 */

const express = require('express');
const cors = require('cors');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'OK', message: 'Servidor ativo' });
});

app.get('/rastreio/:codigo', async (req, res) => {
  const { codigo } = req.params;

  if (!codigo) {
    return res.status(400).json({
      erro: true,
      mensagem: 'Código inválido'
    });
  }

  try {
    console.log('Rastreando:', codigo);

    // NOVO ENDPOINT DESCOBERTO
    const url = `https://spx.com.br/shipment/order/open/order/get_order_info?spx_tn=${codigo}&language_code=pt`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': `https://spx.com.br/track?${codigo}`, // OBRIGATÓRIO PARA EVITAR BLOQUEIO
        'X-Requested-With': 'XMLHttpRequest'
      }
    });

    if (!response.ok) {
      throw new Error(`Erro na API SPX: ${response.status}`);
    }

    const data = await response.json();

    // Validação do retorno da SPX (retcode 0 significa sucesso)
    if (!data || data.retcode !== 0 || !data.data || !data.data.sls_tracking_info) {
      return res.status(404).json({
        status: "Não encontrado",
        eventos: [{ descricao: "Sua busca não gerou resultados" }]
      });
    }

    const slsInfo = data.data.sls_tracking_info;
    const records = slsInfo.records || [];

    // Mapeamento de status baseado no milestone do evento mais recente
    const statusMap = {
      1: "Em preparação",
      2: "Em trânsito",
      3: "Em trânsito",
      4: "Saiu para entrega",
      5: "Entregue"
    };

    let status = "Em processamento";
    if (records.length > 0) {
      const lastMilestone = records[0].milestone_code;
      status = statusMap[lastMilestone] || "Em trânsito";
    }

    // Normaliza os eventos para o formato que sua index espera
    const eventos = records
      .filter(item => item.display_flag_v2 > 0) // Apenas eventos visíveis
      .map(item => {
        // Converte timestamp para data legível
        const date = new Date(item.actual_time * 1000);
        const dataFormatada = date.toLocaleString('pt-BR', { 
          day: '2-digit', 
          month: '2-digit', 
          year: 'numeric', 
          hour: '2-digit', 
          minute: '2-digit' 
        });

        return {
          data: dataFormatada,
          descricao: item.description || item.seller_description
        };
      });

    return res.json({
      status,
      eventos
    });

  } catch (erro) {
    console.error('ERRO REAL:', erro.message);

    return res.status(500).json({
      erro: true,
      mensagem: "Erro ao consultar rastreio. Tente novamente mais tarde."
    });
  }
});

app.get('/', (req, res) => {
  res.json({
    nome: 'API Sermente',
    status: 'online'
  });
});

app.listen(PORT, () => {
  console.log(`Servidor rodando na porta ${PORT}`);
});
