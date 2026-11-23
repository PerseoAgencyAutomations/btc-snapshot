# btc-snapshot

Um comando, uma leitura no terminal de onde o Bitcoin está: posição no ciclo, on-chain,
sentimento, rendimento em DeFi e o contexto macro do Brasil.

Sem chave de API e sem dependência. Usa só a biblioteca padrão do Python.

## Fontes

| Fonte | O que entrega |
|---|---|
| Coin Metrics community API | Preço diário desde 2010, MVRV (preço realizado = preço / MVRV), endereços ativos |
| alternative.me | Índice de medo e ganância dos últimos 7 dias |
| mempool.space | Hashrate (1 ano), altura do bloco, dias até o próximo halving |
| DefiLlama yields | Maiores pools de empréstimo em BTC (TVL acima de US$ 100 milhões) e o APY de cada um |
| Banco Central (SGS) | Meta da Selic (série 432) e dólar PTAX (série 1) |

## O que calcula

- Queda desde o topo histórico e dias desde o topo
- Distância até o preço realizado
- Média móvel de 200 semanas e o múltiplo de Mayer (preço / média de 200 dias)
- Retorno em 7, 30 e 365 dias
- Dias estimados até o próximo halving (bloco 1.050.000, a 10 minutos por bloco)

## Painel no ar

O `--html` também grava um painel estático: cartões com os indicadores, gráfico do ciclo de 5 anos
(preço, preço realizado e média de 200 semanas, em escala log), barras do índice de medo e ganância,
hashrate e a tabela de DeFi. Os gráficos são SVG gerados pelo próprio script, então continua sem
dependência. O modo claro e o escuro seguem o sistema.

Um workflow do GitHub Actions (`.github/workflows/pages.yml`) roda o script todo dia às 09:15 UTC e
publica o resultado no GitHub Pages.

No ar: https://perseoagencyautomations.github.io/btc-snapshot/

## Tolerância a falha

Cada fonte roda sozinha. Se uma API cai, aquela seção mostra o erro (no terminal e no painel) e o
resto continua.

## Uso

```bash
python3 btc_snapshot.py                        # leitura no terminal
python3 btc_snapshot.py --html site/index.html # terminal e painel
```

## Exemplo de saída (21/11/2026)

```
[Coin Metrics, fecho 2026-11-20]
  preço US$ 58,851 | ATH US$ 124,824 em 2025-10-06 | queda -52.9% | 410 dias desde o ATH
  MVRV 1.10 | preço realizado US$ 53,262 | distância +10.5%
  média 200 semanas US$ 68,061 (-13.5%) | Mayer (200d) 0.81
  retorno 7d -13.6%
  retorno 30d -30.1%
  retorno 365d -32.3%
[alternative.me] Fear & Greed hoje 12 (medo extremo), 7d: ['12', '12', '10', '11', '12', '10', '10']
[mempool.space] hashrate 976 EH/s | 1 ano atrás 1,152 | pico 1a 1,245
  bloco ~976,941 | próximo halving (bloco 1.050.000) em ~507 dias
```

## Aviso

É leitura de dados, não recomendação de investimento.
