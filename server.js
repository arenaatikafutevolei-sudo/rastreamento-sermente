/**
 * Servidor de Rastreamento Sermente - OTIMIZADO PARA RAILWAY
 */

const express = require('express');
const cors = require('cors');
const puppeteer = require('puppeteer');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK' });
});

// Endpoint de rastreio
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
    console.log('Rastreando:', codigo);

    browser = await puppeteer.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--single-process',
        '--no-zygote'
      ]
    });

    const page = await browser.newPage();

    await page.setViewport({ width: 1280, height: 800 });

    page.setDefaultTimeout(30000);
    page.setDefaultNavigationTimeout(30000);

    await page.setUserAgent(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    );

    const url = `https://spx.com.br/track?${encodeURIComponent(codigo)}`;

    await page.goto(url, { waitUntil: 'domcontentloaded' });

    // esperar carregar
    await new Promise(resolve => setTimeout(resolve, 3000));

    const dados = await page.evaluate(() => {
      const resultado = {
        status: 'Não encontrado',
        eventos: []
      };

      const texto = document.body.innerText;

      if (texto.includes('não gerou resultados') || texto.includes('não encontrado')) {
        return resultado;
      }

      resultado.status = 'Em transporte';

      return resultado;
    });

    await browser.close();

    res.json({
      sucesso: true,
      codigo,
      ...dados
    });

  } catch (erro) {
    console.error('Erro:', erro.message);

    if (browser) {
      try { await browser.close(); } catch {}
    }

    res.status(500).json({
      erro: true,
      mensagem: 'Erro ao rastrear',
      detalhe: erro.message
    });
  }
});

// 404
app.use((req, res) => {
  res.status(404).json({ erro: true, mensagem: 'Rota não encontrada' });
});

// Start
app.listen(PORT, () => {
  console.log('Servidor rodando na porta', PORT);
});