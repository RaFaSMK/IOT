# Temperaturas com resposta gradual — 23/10/2026

O usuário pediu para diminuir as oscilações rápidas da temperatura na apresentação.
A alteração foi feita nos sinais do simulador, antes de MQTT, banco e inferência;
não é apenas uma suavização visual do gráfico.

- Ambiente: ruído por amostra reduzido de 0,25 para 0,05 °C de desvio padrão.
  O ciclo diário, a faixa sazonal e o relógio de cinco minutos simulados por
  leitura a cada dois segundos continuam iguais.
- Compressor: resposta térmica causal de primeira ordem, com constante de tempo
  de 20 minutos simulados. O aquecimento e o resfriamento deixam de saltar
  instantaneamente ao mudar o estado do compressor. Corrente, vibração e taxa
  de desgaste não foram suavizadas.
- Água: aquecimento e resfriamento quatro vezes mais lentos. Os limites da regra
  de refrigeração configurados pelo usuário foram preservados.

A função térmica é compartilhada com o gerador de datasets e adapta o coeficiente
ao intervalo de amostragem. O processamento vetorizado e o processamento passo
a passo produzem o mesmo resultado, sem observar dados futuros. Novos datasets
e modelos registram o perfil `thermal-20min-v1`; artefatos anteriores continuam
preservados e identificados como anteriores ao novo perfil.

## Verificações

- 38 testes Python aprovados, incluindo causalidade, equivalência entre lote e
  execução em três cadências, resfriamento gradual e redução dos saltos.
- Comparação reproduzível com a implementação do commit `73f4ada`, seed 42,
  200 leituras e sequência desligado → ligado → desligado:

| Medição | Maior salto antes | Maior salto depois |
|---|---:|---:|
| Ambiente | 1,34 °C | 0,37 °C |
| Água | 0,38 °C | 0,07 °C |
| Compressor | 11,60 °C | 2,60 °C |

Esses máximos descrevem o ensaio, não limites absolutos para qualquer cenário.

- Modelo ativo `e6d27772-bdb9-49d1-b74c-1fa84e6e1843` reavaliado sem novo treino:
  três cenários normais, sem prazo de RUL indevido e saúde entre 98,12 e 99,67;
  seis cenários de falha com RUL numérica e tendência decrescente. MAE de RUL
  dos cenários de falha ficou entre 0,169 e 0,727 h de operação simuladas.
- Foram atualizados os serviços simulator, generator e trainer.
- Telemetria real por WebSocket conferida em 12 amostras: maior mudança de
  0,27 °C no ambiente, 0,06 °C na água e 2,12 °C no compressor, incluindo partida.
  Após completar a janela, a inferência voltou a `ready`, saúde 99,13/100, sem
  prazo de RUL indevido em condição saudável. Os 14 serviços estavam saudáveis.

O modelo mantido foi treinado no perfil anterior. Os ensaios acima verificam seu
comportamento no novo perfil sintético; não refazem a calibração das faixas. As
métricas da tela Treinamento continuam sendo as do dataset usado naquele treino,
e não novas métricas de teste do perfil térmico. Para novas métricas/calibração,
é necessário gerar um novo dataset e treinar novamente.
