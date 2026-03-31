/**
 * Servidor de Rastreamento Sermente
 * Backend para consultar rastreamento de pedidos via SPX Express
 * 
 * Autor: Sermente E-commerce
 * Data: 2026
 */

const express = require('express');
const cors = require('cors');
const puppeteer = require('puppeteer-core');
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
 *     { 
 *       "descricao": "Pedido em rota de entrega para seu endereço",
 *       "data": "18 Mar 2026", 
 *       "hora": "16:21:05",
 *       "local": "São Bernardo do Campo - SP"
 *     }
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
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium',
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

    // Extrair dados da página
    const dados = await page.evaluate(() => {
      const resultado = {
        status: 'Informação não disponível',
        eventos: []
      };

      // Obter todo o texto da página
      const pageText = document.body.innerText;
      
      // Verificar se houve erro
      if (pageText.includes('não gerou resultados') || pageText.includes('não encontrado')) {
        resultado.status = 'Código de rastreio não encontrado';
        return resultado;
      }

      // ============================================
      // EXTRAIR STATUS ATUAL
      // ============================================
      
      // Procurar por status na página
      const statusPatterns = [
        'Em trânsito',
        'Saiu para entrega',
        'Entregue',
        'Pendente Envio',
        'Processando'
      ];

      for (let status of statusPatterns) {
        if (pageText.includes(status)) {
          resultado.status = status;
          break;
        }
      }

      // ============================================
      // EXTRAIR EVENTOS DA TIMELINE
      // ============================================
      
      // Padrões para extrair dados
      const horaPattern = /(\d{2}:\d{2}:\d{2})/;
      const dataPattern = /(\d{1,2}\s+[A-Za-z]+\s+\d{4})/;
      
      // Dividir o texto em linhas
      const linhas = pageText.split('\n').filter(l => l.trim().length > 0);
      
      let i = 0;
      while (i < linhas.length) {
        const linha = linhas[i].trim();
        
        // Procurar por padrão de hora
        const horaMatch = linha.match(horaPattern);
        
        if (horaMatch) {
          const hora = horaMatch[1];
          let data = '';
          let descricao = '';
          let local = '';
          
          // A próxima linha geralmente contém a data
          if (i + 1 < linhas.length) {
            const proximaLinha = linhas[i + 1].trim();
            const dataMatch = proximaLinha.match(dataPattern);
            
            if (dataMatch) {
              data = dataMatch[1];
              
              // A próxima linha após a data é a descrição
              if (i + 2 < linhas.length) {
                descricao = linhas[i + 2].trim();
                
                // Extrair local da descrição (geralmente entre : e - ou no final)
                const localMatch = descricao.match(/:\s*([^-]+)\s*-\s*([A-Z]{2})/);
                if (localMatch) {
                  local = localMatch[1].trim() + ' - ' + localMatch[2];
                } else {
                  // Tentar extrair apenas o estado (UF)
                  const ufMatch = descricao.match(/([A-Z]{2})(?:\s|$)/);
                  if (ufMatch) {
                    local = ufMatch[1];
                  }
                }
              }
              
              // Adicionar evento se temos pelo menos hora e data
              if (hora && data) {
                resultado.eventos.push({
                  hora: hora,
                  data: data,
                  descricao: descricao,
                  local: local
                });
              }
              
              // Pular as próximas linhas já processadas
              i += 3;
              continue;
            }
          }
        }
        
        i++;
      }

      return resultado;
    });

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
