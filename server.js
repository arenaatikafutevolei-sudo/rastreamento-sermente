/**
 * Servidor de Rastreamento Sermente
 * Backend para consultar rastreamento de pedidos via SPX Express
 * 
 * Autor: Sermente E-commerce
 * Data: 2026
 */

const express = require('express');
const cors = require('cors');
const puppeteer = require('puppeteer');
const axios = require('axios');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Rota de health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', message: 'Servidor de rastreamento ativo' });
});

/**
 * Endpoint para rastrear pedidos na SPX Express
 * GET /rastreio/:codigo
 * 
 * Parâmetros:
 * - codigo: Código de rastreio do pedido
 * 
 * Retorna:
 * {
 *   "status": "Em transporte",
 *   "eventos": [
 *     { "descricao": "Objeto postado", "data": "10/03/2026", "hora": "14:30", "local": "São Paulo - SP" }
 *   ]
 * }
 */
app.get('/rastreio/:codigo', async (req, res) => {
  const { codigo } = req.params;

  // Validação básica do código de rastreio
  if (!codigo || codigo.trim().length === 0) {
    return res.status(400).json({
      erro: true,
      mensagem: 'Código de rastreio inválido'
    });
  }

  let browser;

  try {
    // Inicializar Puppeteer com opções de sandbox desabilitadas
    browser = await puppeteer.launch({
      headless: 'new',
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu'
      ]
    });

    // Criar nova página
    const page = await browser.newPage();

    // Definir timeout para a página
    page.setDefaultTimeout(30000);
    page.setDefaultNavigationTimeout(30000);
    
    // Configurar user agent para evitar bloqueios
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

    // Interceptar requisições de rede para capturar dados da API
    const requestsCapturados = [];
    const responsesCapturados = [];

    await page.on('response', async (response) => {
      try {
        const url = response.url();
        const status = response.status();

        // Capturar respostas que possam conter dados de rastreamento
        if (url.includes('track') || url.includes('tracking') || url.includes('rastr') || status === 200) {
          const contentType = response.headers()['content-type'] || '';
          
          if (contentType.includes('application/json')) {
            try {
              const data = await response.json();
              responsesCapturados.push({
                url: url,
                data: data,
                timestamp: new Date().toISOString()
              });
            } catch (e) {
              // Ignorar erros ao fazer parse de JSON
            }
          }
        }
      } catch (e) {
        // Ignorar erros
      }
    });

    // URL da SPX Express com o código de rastreio
    const url = `https://spx.com.br/track?${encodeURIComponent(codigo)}`;

    console.log(`[${new Date().toISOString()}] Rastreando: ${codigo}`);
    console.log(`URL: ${url}`);

    // Acessar a página
    await page.goto(url, { 
      waitUntil: 'networkidle2',
      timeout: 30000
    }).catch(err => {
      console.log('Erro ao navegar:', err.message);
    });

    // Aguardar um pouco para a página carregar completamente
    await page.waitForTimeout(2000);

    // Extrair dados da página usando múltiplas estratégias
    const dados = await page.evaluate(() => {
      const resultado = {
        status: 'Informação não disponível',
        eventos: [],
        resumo: {
          total_eventos: 0,
          primeiro_evento: null,
          ultimo_evento: null
        },
        debug: {
          html_length: document.documentElement.innerHTML.length,
          body_text_length: document.body.innerText.length
        }
      };

      // Obter todo o texto da página
      const pageText = document.body.innerText;
      
      // Verificar se houve erro
      if (pageText.includes('não gerou resultados') || pageText.includes('não encontrado')) {
        resultado.status = 'Código de rastreio não encontrado';
        return resultado;
      }

      // ============================================
      // ESTRATÉGIA 1: Procurar por estruturas React
      // ============================================
      
      // Procurar por elementos que contenham informações de rastreamento
      const allText = document.body.innerText;
      
      // Tentar extrair status de padrões comuns
      const statusPatterns = [
        /Status[:\s]+([^\n]+)/i,
        /Situação[:\s]+([^\n]+)/i,
        /Entrega[:\s]+([^\n]+)/i,
        /Pedido[:\s]+([^\n]+)/i
      ];

      for (let pattern of statusPatterns) {
        const match = allText.match(pattern);
        if (match && match[1]) {
          resultado.status = match[1].trim();
          break;
        }
      }

      // ============================================
      // ESTRATÉGIA 2: Procurar por eventos em divs
      // ============================================
      
      // Procurar por padrões de data (DD/MM/YYYY ou DD/MM)
      const datePattern = /(\d{1,2}\/\d{1,2}(?:\/\d{4})?)/g;
      const timePattern = /(\d{1,2}:\d{2}(?::\d{2})?)/g;
      
      // Procurar por divs que contenham eventos
      const allDivs = document.querySelectorAll('div, span, p, li');
      const eventosEncontrados = new Map();

      for (let element of allDivs) {
        const text = element.innerText || element.textContent || '';
        
        // Verificar se contém padrão de data
        if (datePattern.test(text)) {
          const dateMatch = text.match(datePattern);
          const timeMatch = text.match(timePattern);
          
          if (dateMatch) {
            const data = dateMatch[0];
            const hora = timeMatch ? timeMatch[0] : '';
            
            // Usar o texto do elemento como descrição
            let descricao = text.replace(datePattern, '').replace(timePattern, '').trim();
            
            // Se a descrição estiver vazia, procurar em elementos vizinhos
            if (!descricao || descricao.length < 3) {
              if (element.parentElement) {
                descricao = element.parentElement.innerText || element.parentElement.textContent || '';
              }
            }
            
            // Limpar descrição
            descricao = descricao.replace(datePattern, '').replace(timePattern, '').trim();
            descricao = descricao.substring(0, 100); // Limitar tamanho
            
            if (descricao && descricao.length > 3) {
              const chave = data + hora + descricao;
              if (!eventosEncontrados.has(chave)) {
                eventosEncontrados.set(chave, {
                  descricao: descricao,
                  data: data,
                  hora: hora,
                  local: ''
                });
              }
            }
          }
        }
      }

      // Converter Map para Array
      resultado.eventos = Array.from(eventosEncontrados.values());

      // ============================================
      // ESTRATÉGIA 3: Procurar em tabelas
      // ============================================
      
      if (resultado.eventos.length === 0) {
        const tables = document.querySelectorAll('table');
        for (let table of tables) {
          const rows = table.querySelectorAll('tr');
          for (let row of rows) {
            const cells = row.querySelectorAll('td, th');
            if (cells.length >= 2) {
              const evento = {
                descricao: cells[0].innerText || cells[0].textContent || '',
                data: cells.length > 1 ? (cells[1].innerText || cells[1].textContent || '') : '',
                hora: cells.length > 2 ? (cells[2].innerText || cells[2].textContent || '') : '',
                local: cells.length > 3 ? (cells[3].innerText || cells[3].textContent || '') : ''
              };
              
              if (evento.descricao && evento.descricao.length > 3) {
                resultado.eventos.push(evento);
              }
            }
          }
        }
      }

      // ============================================
      // ESTRATÉGIA 4: Procurar em listas
      // ============================================
      
      if (resultado.eventos.length === 0) {
        const lists = document.querySelectorAll('ul, ol');
        for (let list of lists) {
          const items = list.querySelectorAll('li');
          for (let item of items) {
            const text = item.innerText || item.textContent || '';
            const dateMatch = text.match(datePattern);
            
            if (dateMatch) {
              const evento = {
                descricao: text.replace(datePattern, '').replace(timePattern, '').trim(),
                data: dateMatch[0],
                hora: text.match(timePattern) ? text.match(timePattern)[0] : '',
                local: ''
              };
              
              if (evento.descricao && evento.descricao.length > 3) {
                resultado.eventos.push(evento);
              }
            }
          }
        }
      }

      // Remover duplicatas e ordenar
      const eventosUnicos = [];
      const chaves = new Set();
      
      for (let evento of resultado.eventos) {
        const chave = evento.descricao + evento.data;
        if (!chaves.has(chave)) {
          chaves.add(chave);
          eventosUnicos.push(evento);
        }
      }
      
      resultado.eventos = eventosUnicos;

      // Atualizar resumo
      resultado.resumo.total_eventos = resultado.eventos.length;
      if (resultado.eventos.length > 0) {
        resultado.resumo.primeiro_evento = resultado.eventos[0];
        resultado.resumo.ultimo_evento = resultado.eventos[resultado.eventos.length - 1];
      }

      return resultado;
    });

    // Se não encontrou dados na página, tentar usar requisições capturadas
    if (dados.eventos.length === 0 && responsesCapturados.length > 0) {
      console.log('Tentando extrair dados das requisições capturadas...');
      
      for (let response of responsesCapturados) {
        if (response.data && typeof response.data === 'object') {
          // Procurar por campos de rastreamento
          const jsonStr = JSON.stringify(response.data);
          
          if (jsonStr.includes('track') || jsonStr.includes('status') || jsonStr.includes('event')) {
            console.log('Dados potenciais encontrados:', response.url);
            
            // Tentar extrair eventos do JSON
            if (Array.isArray(response.data)) {
              dados.eventos = response.data.slice(0, 10).map(item => ({
                descricao: item.description || item.descricao || item.title || 'Evento',
                data: item.date || item.data || item.timestamp || '',
                hora: item.time || item.hora || '',
                local: item.location || item.local || item.city || ''
              }));
            } else if (response.data.events || response.data.eventos) {
              const events = response.data.events || response.data.eventos;
              if (Array.isArray(events)) {
                dados.eventos = events.slice(0, 10).map(item => ({
                  descricao: item.description || item.descricao || item.title || 'Evento',
                  data: item.date || item.data || item.timestamp || '',
                  hora: item.time || item.hora || '',
                  local: item.location || item.local || item.city || ''
                }));
              }
            }
          }
        }
      }
    }

    // Fechar o navegador
    await browser.close();

    // Retornar dados
    return res.json(dados);

  } catch (erro) {
    console.error(`[${new Date().toISOString()}] Erro ao rastrear ${codigo}:`, erro.message);
    
    if (browser) {
      try {
        await browser.close();
      } catch (e) {
        // Ignorar erro ao fechar
      }
    }

    return res.status(500).json({
      erro: true,
      mensagem: 'Erro ao rastrear pedido. Tente novamente mais tarde.',
      detalhes: process.env.NODE_ENV === 'development' ? erro.message : undefined
    });
  }
});

// Rota raiz
app.get('/', (req, res) => {
  res.json({
    nome: 'API de Rastreamento Sermente',
    versao: '1.0.0',
    endpoints: {
      health: 'GET /health',
      rastreio: 'GET /rastreio/:codigo'
    }
  });
});

// Iniciar servidor
app.listen(PORT, () => {
  console.log(`Servidor de rastreamento rodando em http://localhost:${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
  console.log(`Rastreamento: http://localhost:${PORT}/rastreio/{codigo}`);
});
