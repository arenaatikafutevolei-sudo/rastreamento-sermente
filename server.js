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
 *     { "descricao": "Objeto postado", "data": "10/03/2026" }
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
    // Estas opções são necessárias para ambientes como Railway
    browser = await puppeteer.launch({
      headless: 'new',
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--single-process' // Apenas para ambientes sem restrições de memória
      ]
    });

    // Criar nova página
    const page = await browser.newPage();

    // Definir timeout para a página
    page.setDefaultTimeout(20000);
    page.setDefaultNavigationTimeout(20000);
    
    // Configurar user agent para evitar bloqueios
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');

    // URL da SPX Express com o código de rastreio
    // A página de rastreamento está em: https://spx.com.br/track?{codigo}
    const url = `https://spx.com.br/track?${encodeURIComponent(codigo)}`;

    console.log(`[${new Date().toISOString()}] Rastreando: ${codigo}`);
    console.log(`URL: https://spx.com.br/track?${encodeURIComponent(codigo)}`);

    // Acessar a página
    // Usar 'domcontentloaded' para páginas que usam React/Vue
    await page.goto(url, { waitUntil: 'domcontentloaded' });

    // Aguardar o carregamento completo dos elementos
    // Aguardar um pouco para a página carregar (React/Vue rendering)
    await page.waitForTimeout(3000);
    
    // Tentar aguardar por elementos de rastreamento
    await page.waitForSelector('input, button, div', {
      timeout: 5000
    }).catch(() => null);

    // Extrair dados da página
    const dados = await page.evaluate(() => {
      // Objeto para armazenar os dados extraídos
      const resultado = {
        status: 'Informação não disponível',
        eventos: []
      };

      // Obter todo o texto da página
      const pageText = document.body.innerText;
      
      // Verificar se houve erro (ex: "Sua busca não gerou resultados")
      if (pageText.includes('não gerou resultados') || pageText.includes('não encontrado')) {
        resultado.status = 'Código de rastreio não encontrado';
        return resultado;
      }

      // Tentar extrair o status atual
      // Procura por elementos comuns que contêm o status
      const statusElements = document.querySelectorAll(
        '.tracking-status, .status, [class*="status"], .current-status, .pedido-status, [class*="Status"]'
      );

      if (statusElements.length > 0) {
        const statusText = statusElements[0].textContent.trim();
        if (statusText && statusText.length > 0) {
          resultado.status = statusText;
        }
      }

      // Se não encontrou, tenta buscar por padrões de texto
      if (resultado.status === 'Informação não disponível') {
        const statusMatch = pageText.match(/Status[:\s]+(.*?)(?:\n|$)/i);
        if (statusMatch) {
          resultado.status = statusMatch[1].trim();
        }
      }

      // Extrair eventos/timeline
      // Procura por elementos que contêm os eventos de rastreamento
      const eventElements = document.querySelectorAll(
        '.event, .timeline-item, [class*="event"], [class*="timeline"], .tracking-event, .rastreamento-evento, [class*="Event"]'
      );

      if (eventElements.length > 0) {
        eventElements.forEach((element) => {
          const descricao = element.querySelector(
            '.description, .title, .event-title, [class*="description"], [class*="title"], [class*="Description"], [class*="Title"]'
          );
          const data = element.querySelector(
            '.date, .time, .data, [class*="date"], [class*="time"], [class*="Date"], [class*="Time"]'
          );

          if (descricao && descricao.textContent.trim()) {
            resultado.eventos.push({
              descricao: descricao.textContent.trim(),
              data: data ? data.textContent.trim() : 'Data não disponível'
            });
          }
        });
      }

      // Se não encontrou eventos estruturados, tenta extrair de forma alternativa
      if (resultado.eventos.length === 0) {
        const rows = document.querySelectorAll('tr, .row, [class*="row"]');
        rows.forEach((row) => {
          const cells = row.querySelectorAll('td, .cell, [class*="cell"]');
          if (cells.length >= 2) {
            const descricao = cells[0].textContent.trim();
            const data = cells[cells.length - 1].textContent.trim();
            if (descricao && data) {
              resultado.eventos.push({
                descricao,
                data
              });
            }
          }
        });
      }

      return resultado;
    });

    // Fechar o navegador
    await browser.close();

    // Retornar os dados extraídos
    return res.json({
      sucesso: true,
      codigo,
      ...dados
    });

  } catch (erro) {
    console.error(`[${new Date().toISOString()}] Erro ao rastrear ${codigo}:`, erro.message);

    // Fechar o navegador em caso de erro
    if (browser) {
      try {
        await browser.close();
      } catch (e) {
        console.error('Erro ao fechar navegador:', e.message);
      }
    }

    // Retornar erro apropriado
    if (erro.message.includes('ERR_NAME_NOT_RESOLVED') || 
        erro.message.includes('net::ERR_') ||
        erro.message.includes('ECONNREFUSED')) {
      return res.status(503).json({
        erro: true,
        mensagem: 'Serviço de rastreamento indisponível no momento',
        detalhes: 'Não foi possível conectar ao servidor da SPX Express (https://spx.com.br)'
      });
    }

    if (erro.message.includes('Timeout')) {
      return res.status(504).json({
        erro: true,
        mensagem: 'Timeout ao rastrear pedido',
        detalhes: 'A requisição demorou muito tempo. Tente novamente.'
      });
    }

      return res.status(500).json({
        erro: true,
        mensagem: 'Erro ao rastrear pedido',
        detalhes: erro.message,
        dica: 'Verifique se o código de rastreio está correto e tente novamente.'
      });
  }
});

// Rota 404
app.use((req, res) => {
  res.status(404).json({
    erro: true,
    mensagem: 'Rota não encontrada'
  });
});

// Iniciar servidor
app.listen(PORT, () => {
  console.log(`
╔════════════════════════════════════════════════════════════╗
║         Servidor de Rastreamento Sermente                  ║
║                                                            ║
║  ✓ Servidor rodando na porta ${PORT}                       ║
║  ✓ CORS habilitado                                         ║
║  ✓ Pronto para rastrear pedidos                           ║
║                                                            ║
║  Endpoint: GET /rastreio/:codigo                          ║
║  Health Check: GET /health                                ║
╚════════════════════════════════════════════════════════════╝
  `);
});

// Tratamento de erros não capturados
process.on('unhandledRejection', (reason, promise) => {
  console.error('[Erro não tratado]', reason);
});

// Tratamento de erros não capturados de forma síncrona
process.on('uncaughtException', (error) => {
  console.error('[Exceção não tratada]', error);
});
