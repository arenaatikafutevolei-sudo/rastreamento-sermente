/**
 * Servidor de Rastreamento Sermente (OTIMIZADO PARA RAILWAY)
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

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', message: 'Servidor ativo 🚀' });
});

// Endpoint principal
app.get('/rastreio/:codigo', async (req, res) => {
  const { codigo } = req.params;

  if (!codigo || codigo.trim().length === 0) {
    return res.status(400).json({
      erro: true,
      mensagem: 'Código inválido'
    });
  }

  let browser;

  try {
    console.log(`🔍 Rastreando: ${codigo}`);

    // 🚀 CONFIGURAÇÃO OTIMIZADA PRO RAILWAY
    browser = await puppeteer.launch({
      headless: 'new',
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--single-process'
      ]
    });

    const page = await browser.newPage();

    await page.setUserAgent(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    );

    page.setDefaultTimeout(30000);
    page.setDefaultNavigationTimeout(30000);

    const url = `https://spx.com.br/track?${encodeURIComponent(codigo)}`;

    // 🚀 CARREGAMENTO ESTÁVEL
    await page.goto(url, {
      waitUntil: 'domcontentloaded',
      timeout: 30000
    });

    // 🚀 ESPERA INTELIGENTE
    await page.waitForFunction(() => {
      return document.body && document.body.innerText.length > 100;
    }, { timeout: 10000 }).catch(() => null);

    await page.waitForTimeout(5000);

    // 🚀 CAPTURA CONTROLADA (EVITA TRAVAMENTO)
    const responsesCapturados = [];

    page.on('response', async (response) => {
      try {
        const url = response.url();
        const status = response.status();

        if (
          (url.includes('track') || url.includes('tracking') || url.includes('rastr')) &&
          status === 200
        ) {
          const contentType = response.headers()['content-type'] || '';

          if (contentType.includes('application/json')) {
            const data = await response.json().catch(() => null);
            if (data) {
              responsesCapturados.push({ url, data });
            }
          }
        }
      } catch {}
    });

    // 🚀 SCRAPING PRINCIPAL
    const dados = await page.evaluate(() => {
      const resultado = {
        status: 'Informação não disponível',
        eventos: []
      };

      const text = document.body.innerText;

      if (text.includes('não gerou resultados') || text.includes('não encontrado')) {
        resultado.status = 'Código não encontrado';
        return resultado;
      }

      // STATUS
      const match = text.match(/Status[:\s]+(.*?)(?:\n|$)/i);
      if (match) resultado.status = match[1].trim();

      // EVENTOS POR DATA
      const datePattern = /(\d{1,2}\/\d{1,2}(?:\/\d{4})?)/g;
      const timePattern = /(\d{1,2}:\d{2})/g;

      const elementos = document.querySelectorAll('div, span, p, li');

      elementos.forEach((el) => {
        const txt = el.innerText || '';

        if (datePattern.test(txt)) {
          const data = txt.match(datePattern)?.[0] || '';
          const hora = txt.match(timePattern)?.[0] || '';

          let descricao = txt
            .replace(datePattern, '')
            .replace(timePattern, '')
            .trim()
            .substring(0, 120);

          if (descricao.length > 5) {
            resultado.eventos.push({
              descricao,
              data,
              hora,
              local: ''
            });
          }
        }
      });

      return resultado;
    });

    // 🚀 FALLBACK COM API INTERNA
    if (dados.eventos.length === 0 && responsesCapturados.length > 0) {
      for (let r of responsesCapturados) {
        const d = r.data;

        if (Array.isArray(d)) {
          dados.eventos = d.slice(0, 10).map(item => ({
            descricao: item.description || item.title || 'Evento',
            data: item.date || '',
            hora: item.time || '',
            local: item.location || ''
          }));
        } else if (d?.events || d?.eventos) {
          const events = d.events || d.eventos;

          if (Array.isArray(events)) {
            dados.eventos = events.slice(0, 10).map(item => ({
              descricao: item.description || item.title || 'Evento',
              data: item.date || '',
              hora: item.time || '',
              local: item.location || ''
            }));
          }
        }
      }
    }

    await browser.close();

    // 🚀 PROTEÇÃO FINAL
    if (!dados.status || dados.status.length < 3) {
      dados.status = 'Em processamento';
    }

    if (!dados.eventos) dados.eventos = [];

    return res.json({
      sucesso: true,
      codigo,
      ...dados
    });

  } catch (erro) {
    console.error('❌ ERRO:', erro.message);

    if (browser) {
      try { await browser.close(); } catch {}
    }

    return res.status(500).json({
      erro: true,
      mensagem: 'Erro ao rastrear',
      detalhes: erro.message
    });
  }
});

// Rota raiz
app.get('/', (req, res) => {
  res.json({
    nome: 'API Sermente',
    status: 'online'
  });
});

// Start
app.listen(PORT, () => {
  console.log(`🚀 Rodando na porta ${PORT}`);
});