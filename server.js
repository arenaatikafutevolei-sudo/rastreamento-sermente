/**
 * Servidor de Rastreamento Sermente (VERSÃO FINAL - API DIRETA SPX)
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

    const response = await fetch(
      `https://spx.com.br/api/v2/tracking?trackingNumber=${codigo}`,
      {
        method: 'GET',
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
          'Accept': 'application/json',
          'Referer': 'https://spx.com.br/',
          'Origin': 'https://spx.com.br'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Erro na API SPX: ${response.status}`);
    }

    const data = await response.json();

    // 🔥 validação segura
    if (!data || !data.data) {
      throw new Error('Rastreamento não encontrado');
    }

    const eventos = data.data.events || [];

    // 👇 normaliza status
    let status = data.data.status || 'Em processamento';

    return res.json({
      status,
      eventos
    });

  } catch (erro) {
    console.error('ERRO REAL:', erro.message);

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