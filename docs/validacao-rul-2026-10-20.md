# RUL: investigação e validação de 20/10/2026

O gráfico variava cerca de mil horas em poucos minutos com o compressor saudável.
O diagnóstico reproduziu esse comportamento sem alterar o equipamento em uso.

## Causa e limite dos dados

O gerador sorteia tempos de falha distintos para cada equipamento. Antes do início
do desgaste, equipamentos com vidas muito diferentes têm praticamente as mesmas
temperatura, corrente e vibração. O regressor não recebe idade nem histórico de
manutenção. Portanto, esses sinais não identificam um prazo de falha único.
Ruído e carga alteravam a média prevista, que era exibida com precisão excessiva.

Há também uma diferença temporal: o dataset padrão amostra a cada cinco minutos;
o simulador publica a cada dois segundos e acelera ciclos e desgaste para a demo.
Não existe calibração dessa RUL em horas reais. As faixas abaixo não resolvem essa
diferença nem substituem dados de vida completos, idade/horas de operação e um
ensaio com a mesma cadência de treino e uso.

## Mudanças

- Cada novo treino mede o percentil de erro absoluto nominal de 90% na validação,
  separado por faixas de saúde **prevista** (0–40, 40–70, 70–90, 90–100).
  O teste separado apenas avalia a cobertura, sem ajustar as faixas.
- Com saúde >= 90, o prazo pontual é inconclusivo por falta de evidência de desgaste.
  Nas outras condições, também é inconclusivo se o raio de erro excede o maior
  entre 48 horas e 25% da estimativa. Essa é uma política explícita de apresentação,
  não uma garantia estatística de confiança.
- O valor bruto permanece no evento em `rul_estimate_hours`. `rul_hours` fica nulo
  quando inconclusivo; motivo e faixa experimental são enviados no mesmo evento.
- Saúde e falha continuam sendo avaliadas pelas leituras. Não se impôs uma curva
  monotônica nem se restringiram variações arbitrariamente.
- O alerta de RUL só é confirmado quando o limite superior inteiro está abaixo
  de 48 h. Uma RUL inconclusiva não comprova condição segura; saúde baixa ainda
  abre alerta de forma independente.
- Desligamento, aquecimento, RUL inconclusiva e cortes no WebSocket geram lacunas
  nos gráficos. Após pausa de telemetria > 10 s, a inferência coleta nova janela.
- Confirmações visuais são correlacionadas aos comandos enviados nesta sessão;
  comandos automáticos continuam nos eventos e na auditoria.

## Resultados nesta máquina

Dataset existente reutilizado; nova versão ativa:
`ee495d09-68e3-40a2-b8fc-723932599c6f`.
O novo treino preservou os regressores e métricas determinísticos, acrescentando
a avaliação de incerteza. **Não houve ganho na precisão pontual da RUL.**

| Alvo | MAE no teste | RMSE | R² |
|---|---:|---:|---:|
| Saúde | 8,239 pontos | 13,979 | 0,853 |
| RUL | 505,052 h | 647,742 h | 0,396 |

| Saúde prevista | Raio empírico de erro (validação) | Cobertura no teste |
|---|---:|---:|
| 0–40 | 240 h | 65,4% |
| 40–70 | 709 h | 85,4% |
| 70–90 | 984 h | 93,5% |
| 90–100 | 1.438 h | 94,1% |

A cobertura de apenas 65,4% no primeiro grupo confirma a fragilidade fora da
validação. Essas faixas são experimentais, **não intervalos garantidos de 90%**.

Três execuções saudáveis (seeds 42, 7, 123; 960 passos por execução) produziram
saúde entre 99,57 e 99,98. A RUL bruta variou 1.370, 1.064 e 1.138 h,
respectivamente; nenhuma foi publicada como prazo pontual confiável.
Na falha injetada, a saúde final foi 1,4/100; a RUL também permaneceu inconclusiva.
Com o modelo atual, os quatro cenários ensaiados não sustentam prazo pontual.

Verificações executadas:

- Build Vue/TypeScript aprovado.
- 27 testes Python aprovados, incluindo independência do teste na construção das
  faixas, ausência de prazo indevido, limites de alerta e reinício da janela.
- `scripts.check_prediction_stability`: três ciclos normais e falha aprovados.
- Ensaio real `scripts.check_live live`: regra automática, inferência, falha,
  alerta persistido/WebSocket, assistente local em streaming e recuperação aprovados.
  Regra e equipamento restaurados ao final.
- Interface conferida em navegador: RUL inconclusiva com motivo/faixa e confirmação
  manual dos refletores. Refletores devolvidos ao estado desligado.

Para apresentar: explicar saúde como índice estimado e RUL como resultado
experimental ainda inconclusivo. A ativação após vencer a baseline não comprova
que o prazo é identificável, estável ou calibrado em equipamento real.
