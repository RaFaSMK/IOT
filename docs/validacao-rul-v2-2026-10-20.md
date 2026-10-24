# Correção da dinâmica e da RUL — 20/10/2026

> Atualização de 23/10/2026: a [política de exibição](validacao-exibicao-rul-2026-10-23.md)
> passou a mostrar também estimativas de baixa confiança durante a degradação.
> O limite de erro descrito abaixo agora qualifica o valor em vez de ocultá-lo.
> As métricas do modelo permanecem as mesmas; os ensaios abaixo registram a
> política anterior. Condição saudável continua sem prazo identificável.

Este documento substitui, para o estado atual, a conclusão de RUL sempre
inconclusiva de `validacao-rul-2026-10-20.md`. Os dados e modelos antigos foram
preservados nos volumes. As alterações desta etapa integram a publicação na
branch `main`, autorizada pelo usuário em 20/10/2026.

## O que mudou no problema modelado

O modelo anterior tentava inferir a vida de equipamentos saudáveis com tempos de
falha sorteados e sinais semelhantes. Esse prazo não era identificável. Além
disso, treino e execução usavam dinâmicas e escalas temporais distintas.

Agora `aiot/equipment.py` compartilha a física sintética de temperatura, corrente,
vibração, carga e ruído entre gerador e simulador. O laboratório continua
vetorizado por equipamento. Há períodos ligados/desligados, variações individuais,
três modos de falha, ruído, faltantes, outliers e degradação progressiva.

Na nova simulação, cada publicação a cada **2 segundos reais** representa
**5 minutos simulados**. O desgaste avança durante a operação. Após o início
da falha, a fase de degradação do dataset dura de 4 a 14 horas de operação
simuladas; o botão de injeção do simulador usa seis horas. Esse horizonte curto
é uma escolha explícita de demonstração, não uma vida útil de compressor real.

**RUL significa horas de operação simuladas restantes, supondo continuidade da
degradação atual.** Paradas não gastam essas horas. Não significa horas do relógio
real ou uma data no calendário.

As métricas antigas em horizontes de centenas/milhares de horas não são
diretamente comparáveis às novas. Mudaram a dinâmica, a unidade operacional e a
população avaliada: a regressão pontual de RUL é treinada/avaliada somente em
janelas com degradação observável. A baseline usa exatamente a mesma população.

## Features, treino e incerteza

- Três medições do compressor mais a temperatura ambiente, todas observáveis.
  A temperatura do compressor é compensada pela temperatura ambiente.
- Janelas causais com horizonte fixo de 55 minutos simulados e tendências por
  hora. O laboratório pode mudar seu intervalo: a reamostragem usa apenas
  observações já disponíveis no instante avaliado.
- Saúde: ExtraTrees, 64 árvores. RUL: ExtraTrees, 128 árvores, com alvo `log1p`
  e inversa `expm1`, para reduzir o predomínio dos horizontes longos no ajuste.
- Split por equipamento: 60 treino, 20 validação, 20 teste.
- O contrato de features/dinâmica foi versionado (`compressor-v2`). Dados/modelos
  antigos são preservados, mas não são usados com as novas features.
- Relógio simulado é publicado e persistido com a telemetria. Desgaste interno,
  saúde verdadeira e RUL verdadeira **não** são publicados. O contrato rejeita
  rótulos escondidos no objeto de relógio.
- A faixa experimental vem do erro observado na validação, agrupado pelo
  horizonte previsto. Grupos pequenos usam os vizinhos mais próximos da validação.
  O teste mede cobertura; não ajusta essa faixa.
- A política de apresentação conserva o prazo como inconclusivo quando o raio de
  erro excede o maior entre 0,5 h e 25% da estimativa. Em condição saudável
  (saúde >= 90), nem ponto nem faixa de RUL são usados para exibir prazo ou
  acionar alerta: o regressor condicional não foi treinado para essa região.
- Os dados brutos da regressão continuam disponíveis no evento para diagnóstico.
  Não se impôs monotonicidade nem uma suavização para esconder instabilidade.

## Artefatos ativos

Dataset: `ee484586-ac10-4be9-a27f-c647ee097cdb`.

Modelo ativo: `e6d27772-bdb9-49d1-b74c-1fa84e6e1843`.

Configuração: 100 equipamentos, 60 dias, intervalo de 5 minutos, 65% com falha,
três modos, ruído 0,6, faltantes 1%, outliers 0,5%, seed 42.
**1.728.000 amostras / 5.184.000 leituras.**

Ambos os jobs foram disparados pela API, passaram pelas filas RabbitMQ e
terminaram. A nova versão venceu as baselines e foi ativada pelo treinador,
sem reiniciar a inferência para trocar o modelo.

Os artefatos antigos `ac1f9118...`, `0a2cdb7e...` e `ee495d09...` continuam
preservados. Ensaios exploratórios estão em `/data/experiments-v2`, separados
dos artefatos registrados no laboratório da aplicação.

| Alvo | MAE teste | RMSE teste | R² teste | MAE baseline |
|---|---:|---:|---:|---:|
| Saúde | 0,536 pontos | 0,784 | 0,991 | 3,910 pontos |
| RUL na degradação | 0,668 h | 0,871 | 0,917 | 2,503 h |

Saúde usou até 50 mil amostras por conjunto. A RUL teve 2.845 amostras de
treino, 632 de validação e 1.018 de teste, dos equipamentos separados.
O volume total inclui principalmente operação normal, como ocorre em
manutenção preditiva. Não afirmar que todas as 5,18 milhões de leituras foram
usadas para ajustar a regressão de RUL.

Para não esconder o efeito da maioria saudável no resultado de saúde, também
foi avaliado o subconjunto degradado dos equipamentos de teste: MAE 2,556 pontos,
RMSE 3,282 e R² 0,985, em 1.018 janelas.

## Ensaios fora do dataset

`scripts.check_prediction_stability` usa a classe real do simulador e previsões
em lote. Os rótulos internos são consultados apenas pelo avaliador offline para
medir erro, nunca pela função de previsão ou pela telemetria.

Três cenários normais (seeds 42, 7, 123; 960 passos cada) ficaram com saúde entre
98,28 e 99,76, sem publicar prazo de RUL para condição saudável.

Seis cenários de falha produziram RUL numérica na fase final da degradação.
As três sementes adicionais reservadas ao ensaio final resultaram em:

| Cenário | Seed | MAE de RUL no cenário inteiro | Amostras com prazo publicado | Primeiro → último prazo publicado |
|---|---:|---:|---:|---:|
| Rolamento, duração 6 h | 13579 | 0,266 h | 12 | 0,858 → 0,265 h |
| Superaquecimento, duração 10 h | 24680 | 0,563 h | 15 | 0,991 → 0,119 h |
| Desbalanceamento, duração 4 h | 97531 | 0,643 h | 9 | 0,965 → 0,208 h |

Os três cenários de desenvolvimento (seeds 99, 2026, 314) também passaram.
Não extrapolar esses resultados para outros equipamentos físicos.

**Limitação que permanece:** a política é conservadora e, nesses ensaios, o
prazo pontual apareceu principalmente abaixo de uma hora de operação restante.
No início da degradação ele ainda pode ser inconclusivo; isso é informado na
interface com a faixa experimental. Não prometer RUL pontual durante toda a vida.

As faixas são empíricas, sem garantia de cobertura de 90%. No teste, o grupo
de previsões abaixo de 1 h teve cobertura de aproximadamente 71,8%; os outros
grupos tiveram cerca de 87,3%, 90,9%, 94,9% e 98,5%. Portanto, não apresentar a
faixa como intervalo de confiança certificado. Mais equipamentos/validação e
calibração por equipamento são melhorias possíveis.

## Integração e interface

- Build Vue/TypeScript aprovado; 32 testes Python aprovados.
- Ensaio integrado final aprovado: 12 previsões saudáveis sem faixa/alerta indevido de RUL, regra automática, falha, alerta persistido/WS, oito previsões numéricas de RUL, resposta do LLM local em streaming e recuperação com limpeza do alerta. Regra e equipamento restaurados ao final.
- A RUL publicada caiu de 0,879 para 0,456 h em oito mensagens no ensaio final, passando por MQTT, gateway, RabbitMQ, inferência, API e WS. Um ensaio anterior também observou 0,809 → 0,264 h; nesse ensaio anterior o cliente de teste perdeu o WS ao esperar pelo LLM. O problema era a fila de recepção limitada do próprio ensaio: ela foi ajustada para continuar processando ping/pong durante a espera HTTP, e o ensaio completo foi repetido com sucesso.
- Um ensaio inicial revelou alerta indevido no caso saudável: a faixa de uma
  extrapolação ainda era usada nas regras. Esse caso foi corrigido e entrou no
  teste de regressão; condição saudável não publica faixa nem aciona RUL.
- O script de integração aguarda 12 previsões normais e a limpeza de alertas
  antes de injetar falha. O bloco de restauração cobre inclusive falhas no preparo.
- DLQ: mensagem inválida de QA foi rejeitada; duas leituras preservaram o
  conteúdo. Essas mensagens de teste permanecem na DLQ intencionalmente.
- Minigráficos do 3D passaram a receber estados dos atuadores pelo WS; painel
  dos refletores e gráfico em zero conferidos visualmente no navegador.
- Tela Treinamento distingue versão ativa e último treino não ativado.
- O ensaio de parar o writer para medir acúmulo/drenagem foi bloqueado pela
  aprovação automática, que informou apenas “bloqueado pela política”. Não foi
  repetido por um caminho alternativo. Essa demonstração continua pendente nesta
  rodada. O writer não foi parado pela tentativa rejeitada.
- Um ensaio realmente desconectado da internet também continua pendente.

Conferência final após aplicar a versão: **14 serviços permanentes saudáveis**,
API/dependências OK, modelo `e6d27772...` ativo, nenhum alerta ativo, regra da água
restaurada para ligar acima de 16 °C e desligar abaixo de 10 °C. As sete filas
de serviço estavam vazias com um consumidor cada. A DLQ tinha duas mensagens
inválidas do teste de QA, preservadas intencionalmente. A tela Treinamento foi
conferida no navegador com o dataset de 5.184.000 leituras, split 60/20/20 e as
métricas do modelo ativo.

## Demonstração sugerida

1. Abrir Insights e explicar a escala de tempo indicada na tela.
2. Sem falha, mostrar saúde próxima de 100 e RUL inconclusiva por ausência de
   evidência de degradação. Isso evita inventar um prazo saudável.
3. Injetar falha e acompanhar medições, saúde, faixa experimental e alerta.
4. Perto da fase final, mostrar a RUL numérica e sua tendência decrescente no
   painel e no 3D. Não dizer que os segundos reais são horas reais de vida útil.
5. Perguntar ao assistente sobre a falha e conferir o texto contra os dados.
6. Restaurar o equipamento e observar a resolução após dez previsões normais.

O compressor precisa operar para acumular evidência. A regra normal pode
desligá-lo ao esfriar a água; o script `python -m scripts.check_live live`
ajusta temporariamente a regra para um ensaio contínuo e restaura ao final.

## Pendências para fechar a apresentação

- Ensaiar na máquina da apresentação com a internet desconectada: interface,
  telemetria, comandos, inferência e assistente Ollama local. Baixar as imagens
  Docker e o modelo Ollama antes; preparar o dataset/modelo nessa máquina ou
  transferir os volumes. O push do código não transfere os artefatos locais.
- Repetir a demonstração de persistência da fila: parar somente o consumidor
  writer, observar mensagens acumulando, retomá-lo e conferir a drenagem e as
  leituras no InfluxDB. A tentativa automática desta rodada foi rejeitada pela
  política de aprovação; o teste permanece pendente.
- Ensaiar o roteiro completo com os três papéis, comandos e regra automática,
  falha → RUL → alerta → assistente → restauração, DLQ e consultas aos dois
  bancos. Esses fluxos foram conferidos nesta máquina, mas ainda precisam ser
  repetidos na máquina que será usada na apresentação.

Não há outra correção funcional conhecida impedindo esse ensaio. A RUL continua
experimental, em horas de operação simuladas, com prazo pontual principalmente
na fase final da degradação.
