/**
 * Servidor de Rastreamento Sermente (VERSÃO FINAL COM BYPASS)
 */

const express = require('express');
const cors = require('cors');
const puppeteer = require('puppeteer');
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

  let browser;

  try {
    browser = await puppeteer.launch({
      headless: "new", // 👈 mais estável no Railway
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--window-size=1920,1080'
      ]
    });

    const page = await browser.newPage();

    // 👇 viewport realista
    await page.setViewport({
      width: 1366,
      height: 768
    });

    // 👇 remove detecção de bot
    await page.evaluateOnNewDocument(() => {
      Object.defineProperty(navigator, 'webdriver', {
        get: () => false,
      });
    });

    // 👇 user agent real
    await page.setUserAgent(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'
    );

    const url = `https://spx.com.br/track?trackingNumber=${codigo}`;

    console.log('Rastreando:', codigo);
    console.log('URL:', url);

    await page.goto(url, {
      waitUntil: 'domcontentloaded',
      timeout: 30000
    });

    // 👇 espera carregamento real
    await page.waitForSelector('body', { timeout: 15000 });
    await new Promise(resolve => setTimeout(resolve, 5000));

    const texto = await page.evaluate(() => document.body.innerText);

    if (!texto || texto.length < 50) {
      throw new Error('Página vazia ou bloqueada pela SPX');
    }

    // ==========================
    // EXTRAÇÃO DE DADOS
    // ==========================

    const eventos = [];
    const linhas = texto.split('\n').map(l => l.trim()).filter(Boolean);

    let status = 'Em processamento';

    if (texto.toLowerCase().includes('entregue')) status = 'Entregue';
    else if (texto.toLowerCase().includes('saiu para entrega')) status = 'Saiu para entrega';
    else if (texto.toLowerCase().includes('trânsito')) status = 'Em transporte';

    for (let i = 0; i < linhas.length; i++) {
      if (linhas[i].match(/\d{2}:\d{2}:\d{2}/)) {
        eventos.push({
          hora: linhas[i],
          data: linhas[i + 1] || '',
          descricao: linhas[i + 2] || '',
          local: linhas[i + 3] || ''
        });
      }
    }

    await browser.close();

    return res.json({
      status,
      eventos: eventos.length > 0 ? eventos : [
        { descricao: texto.slice(0, 300) }
      ]
    });

  } catch (erro) {
    console.error('ERRO REAL:', erro.message);

    if (browser) {
      try { await browser.close(); } catch {}
    }

    return res.status(500).json({
      erro: true,
      mensagem: erro.message
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