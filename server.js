/**
 * Servidor de Rastreamento Sermente (VERSÃO OTIMIZADA PARA RAILWAY)
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

// Health Check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', message: 'Servidor ativo 🚀' });
});

// Rota de rastreio
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

    page.setDefaultTimeout(20000);
    page.setDefaultNavigationTimeout(20000);

    const url = `https://spx.com.br/track?${encodeURIComponent(codigo)}`;

    await page.goto(url, { waitUntil: 'domcontentloaded' });

    // Espera inteligente (evita página vazia)
    await page.waitForFunction(() => {
      return document.body && document.body.innerText.length > 100;
    }, { timeout: 10000 }).catch(() => null);

    // Tempo extra pro JS da SPX renderizar
    await page.waitForTimeout(6000);

    const dados = await page.evaluate(() => {
      const resultado = {
        status: 'Informação não disponível',
        eventos: []
      };

      const pageText = document.body.innerText;

      if (
        pageText.includes('não gerou resultados') ||
        pageText.includes('não encontrado')
      ) {
        resultado.status = 'Código não encontrado';
        return resultado;
      }

      // STATUS
      const statusElements = document.querySelectorAll(
        '.tracking-status, .status, [class*="status"], .current-status'
      );

      if (statusElements.length > 0) {
        const txt = statusElements[0].textContent.trim();
        if (txt) resultado.status = txt;
      }

      if (
        resultado.status === 'Informação não disponível' ||
        resultado.status.length < 3
      ) {
        const match = pageText.match(/Status[:\s]+(.*?)(?:\n|$)/i);
        if (match) resultado.status = match[1].trim();
      }

      // EVENTOS
      const eventos = document.querySelectorAll(
        '.event, .timeline-item, [class*="event"], [class*="timeline"]'
      );

      eventos.forEach((el) => {
        const descricao = el.textContent.trim();

        if (descricao && descricao.length > 5) {
          resultado.eventos.push({
            descricao,
            data: '—'
          });
        }
      });

      return resultado;
    });

    await browser.close();

    return res.json({
      sucesso: true,
      codigo,
      ...dados
    });

  } catch (erro) {
    console.error('❌ ERRO:', erro.message);

    if (browser) {
      try {
        await browser.close();
      } catch {}
    }

    return res.status(500).json({
      erro: true,
      mensagem: 'Erro ao rastrear',
      detalhes: erro.message
    });
  }
});

// 404
app.use((req, res) => {
  res.status(404).json({ erro: true, mensagem: 'Rota não encontrada' });
});

// Start
app.listen(PORT, () => {
  console.log(`🚀 Rodando na porta ${PORT}`);
});