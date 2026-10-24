# Checklist do professor — auditoria de 12/10/2026

> **23/10/2026:** a [RUL durante degradação](validacao-exibicao-rul-2026-10-23.md) passou a exibir também estimativas de baixa confiança com faixa experimental. O critério de erro deixou de ocultar o valor. Saúde >= 90 continua sem prazo identificado. As métricas do modelo não mudaram.

> **Revisão de 20/10/2026:** as métricas e evidências abaixo são históricas da dinâmica anterior. O estado atual está na [validação RUL v2](validacao-rul-v2-2026-10-20.md): 5.184.000 leituras, nova escala de tempo compartilhada, RUL condicional à degradação e previsão numérica observada na fase final da falha. Não confundir a precisão do novo alvo operacional com uma previsão de calendário real. As alterações atuais integram a publicação na `main`, autorizada pelo usuário; os artefatos treinados permanecem nos volumes locais. A repetição do ensaio de parar o writer foi bloqueada pela aprovação automática; o ensaio offline na máquina de apresentação continua pendente. A exigência de commits dos outros membros foi excluída pelo usuário.

**Conclusão após as correções de 12/10/2026: os requisitos técnicos conferidos estão implementados e os principais fluxos passaram nos testes.** A ressalva factual do Assistente foi corrigida com respostas baseadas em fatos do backend e seleção estruturada pelo Ollama. O README recebeu o diagrama atual e o roteiro resumido. As alterações foram publicadas na branch main do GitHub. O ensaio no notebook ainda depende do usuário; contribuições do grupo ficaram fora desta rodada por decisão expressa dele.

Base: texto completo enviado pelo usuário nesta conversa, com apresentação em **16/11/2026**, e enunciado preservado em [2Bim.MD](2Bim.MD). O diagrama anexado foi tratado como referência; a inspeção considerou os serviços efetivamente usados no Compose.

Legenda: **OK** = evidência observada; **Parcial** = implementado com ressalva/pendência; **Código** = conferido na implementação, sem ensaio específico de todos os casos; **N/A** = condição que não existe na cena. Uma marca OK não garante nota: o professor exige demonstração funcionando.

## Lista mínima, item por item

| # | Requisito | Resultado | Evidência |
| --- | --- | --- | --- |
| 1 | Vue 3 ou React + TypeScript + Vite | OK | Vue 3; `frontend/package.json`; build novo, sem cache, passou com type-check. |
| 2 | Python + FastAPI + REST | OK | `backend/aiot/app.py`; `/docs` e `/openapi.json` responderam HTTP 200. Node usado somente para compilar o frontend. |
| 3 | WebSocket ao vivo | OK | Teste de integração e interface conectada recebendo telemetria/previsões. |
| 4 | MQTT/Mosquitto nos dois sentidos | OK | Comando Web recebeu confirmação do simulador e estado apareceu na telemetria. Gateway faz MQTT ↔ AMQP. |
| 5 | Pelo menos 3 sensores simulados | OK | Sete: temperatura ambiente, umidade, luminosidade, temperatura da água, temperatura/corrente/vibração do compressor. |
| 6 | Pelo menos 2 atuadores | OK | `cooling` e `floodlights`. |
| 7 | Equipamento preditivo com 3 medições | OK | `compressor_01`: temperatura, corrente e vibração; teste de falha alterou medições e previsões. |
| 8 | Atuador acionado automaticamente | OK | Regra da água religou a refrigeração no teste; limites originais foram restaurados. |
| 9 | Atuador comandado pela Web | OK | Refletores: REST → RabbitMQ → gateway → MQTT → simulador → ack/telemetria. |
| 10 | RabbitMQ, filas, consumidores e tela | OK | Exchange topic, oito filas, sete consumidores operacionais; Mensageria inspecionada. |
| 11 | PostgreSQL e InfluxDB com papéis claros | OK | Cadastro/regra/auditoria/jobs/modelos no PostgreSQL; sensores/highlights no InfluxDB. Edição e restauração de cadastro testadas. |
| 12 | Dashboard, gráficos e histórico | OK | ECharts, histórico consultado na API, dashboard por WebSocket; componentes de gráficos conferidos. |
| 13 | Cadastro/gerenciamento dos dispositivos | OK | Consulta, edição e persistência verificadas; cadastro e desativação implementados com acesso de administrador. |
| 14 | Three.js somente com dados ao vivo | OK | Cena WebGL observada; simulador parado fez aparecer “Sem dados · animações pausadas”, mantendo WebSocket conectado. |
| 15 | Gerador massivo configurável pela UI | OK | Laboratório e parâmetros no código; geração real de **1.555.200 leituras / 518.400 amostras** pela API/fila. |
| 16 | Dois regressores com métricas | OK | Saúde e RUL treinados novamente; métricas, scatter, importância e baseline observados na página Treinamento. |
| 17 | Saúde, RUL, tendência e alertas ao vivo | OK | Página Insights inspecionada durante falha; alerta persistido, entregue e resolvido após reset/histerese. |
| 18 | Assistente local responde sobre os dados | OK após correção | Ollama local seleciona fatos com JSON Schema; backend transmite textos e valores verificados. Quatro cenários reais de LLM conferiram limites, histerese, métricas e arquitetura. |
| 19 | Tudo no Docker Compose, um comando | OK local | `docker compose up -d` iniciou a pilha existente; 14 serviços permanentes com healthcheck. Bootstrap, database-init e model-init encerraram com zero. Instalação limpa em outra máquina não foi ensaiada nesta auditoria. |
| 20 | Código versionado no GitHub | OK publicação na main | Remoto `RaFaSMK/IOT`; commit de código `ea229b8` publicado e hash remoto conferido. A conferência inicial do histórico de autores é registrada abaixo; o usuário excluiu esse assunto do escopo de correção. |

## Fluxos que devem ser demonstrados

- [x] IoT → MQTT → gateway → RabbitMQ → gravador/InfluxDB e API → WebSocket → interface. São consumidores paralelos do barramento; a API consulta o histórico no InfluxDB.
- [x] Web → API → RabbitMQ → gateway → MQTT → atuador → confirmação/estado nas leituras seguintes.
- [x] Laboratório → fila de geração → dataset → fila de treino → artefatos → ativação → inferência da telemetria → RabbitMQ → interface.
- [x] Falha → degradação das medições → regressão → alerta → persistência/PostgreSQL e WebSocket.
- [x] Reset → recuperação das previsões → resolução do alerta após sequência de observações.
- [x] Proposta original da quadra e highlights preservada; o compressor do bebedouro é a evolução de manutenção preditiva.

## Regras detalhadas do 3D

- [x] Three.js e OrbitControls; sem conexão direta ao simulador (`DigitalTwin.vue` lê o store).
- [x] Store atualizado por WebSocket, lido no loop de animação; cena não é reconstruída a cada mensagem.
- [x] Sete sensores, dois atuadores, compressor, botão de highlight e simulador representados pelos mesmos IDs do cadastro padrão.
- [x] Posições guardadas apenas no frontend, em `positions`.
- [x] Cores normal/atenção/crítico/sem dados implementadas a partir de faixa, saúde e alertas (`deviceState`). Cena sem telemetria foi observada em execução.
- [x] Refletor ilumina quando ligado; rotor do compressor gira quando a refrigeração está ligada; amplitude do tremor acompanha vibração.
- [x] Dois elementos ambientais: luz/céu pela luminosidade, nuvens pela umidade. Temperatura da água também altera a cor da água.
- [x] Painel por item: leitura, minigráfico, saúde/RUL e controles dos atuadores.
- [x] Interseção/raycast de clique implementada; seleção alternativa pelo dropdown observada.
- [x] Ausência de dados após dez segundos: aviso e pausa das animações dos dispositivos, com WebSocket ainda conectado.
- [x] InstancedMesh usado nas nuvens.
- [x] N/A: a cena atual não desenha tubulações/cabos; a exigência de pontas conectadas não se aplica a eles.

O cadastro aceita novos IDs, mas a cena tem posições para os dispositivos do cenário atual. Um novo dispositivo físico/simulado exige também adicionar sua posição no frontend; cadastrar um nome isolado não cria telemetria nem um objeto novo automaticamente.

## RabbitMQ e mensageria

- [x] `court.events` e `court.dead` são exchanges topic, confirmados por `rabbitmqctl`.
- [x] Routing keys incluem tipo, quadra e dispositivo, por exemplo `telemetry.court_01.compressor_01`.
- [x] Filas distintas: `court.writer`, `court.inference`, `court.api`, `court.gateway`, `court.rules`, `court.generator`, `court.trainer`; `court.dlq` recebe rejeições.
- [x] Geração/treino executados em consumidores separados, com API retornando job sem esperar todo o processamento.
- [x] JSON validado por `Event`: id, timestamp com fuso, type, device_id, payload, schema_version e correlation_id.
- [x] Mensagem deliberadamente inválida foi rejeitada e preservada; duas inspeções da DLQ não reduziram seu conteúdo.
- [x] Usuários distintos por serviço; `list_users` não mostrou guest. Permissões por fila/exchange e topic_permissions conferidas.
- [x] Página Mensageria mostra mensagens prontas/em entrega, taxas, consumidores, últimas mensagens e inspeção da DLQ.
- [x] Navegador consulta a API da aplicação; somente backend consulta o gerenciamento do RabbitMQ.
- [x] Teste de consumidor parado: **9 mensagens prontas / 0 consumidores** no gravador; retomada terminou em **0 mensagens prontas / 1 consumidor**.

A DLQ tinha **17 mensagens** na inspeção: 15 anteriores à auditoria, com data de 09/10 UTC, e duas cópias do contrato inválido criado por este teste (rejeitado pela API e gateway). Não foram apagadas nem reenviadas. Logs de rejeição dessa mensagem são esperados. O volume restaurado preserva também rejeições antigas; o grupo deve saber explicar a fila.

## Dados sintéticos e IA

- [x] Parâmetros: equipamentos, sensores de cada tipo, dias, intervalo, percentual de falhas, modos rolamento/superaquecimento/desbalanceamento, ruído, faltantes, outliers e semente.
- [x] NumPy por bloco/equipamento e memmap, sem loop Python por leitura (`ml.generate`).
- [x] Degradação gradual, diferenças entre máquinas, ruído, ciclo diário/semanal/sazonal no gerador.
- [x] Saúde contínua 0–100 e tempo até falha são targets do dataset; não entram na telemetria ao vivo. Saúde também permite identificar degradação, em vez de um classificador separado.
- [x] Mínimo de um milhão de leituras; teto de 20 milhões de leituras e dois milhões de amostras. API rejeitou configurações fora desses limites.
- [x] Progresso persistido no job e publicado pelo RabbitMQ; interface acompanha jobs.
- [x] Dataset salvo no volume de artefatos, separado do histórico ao vivo. Bucket `lab` é opcional no enunciado e não foi criado.
- [x] Dois ExtraTreesRegressor: `health` e `rul_hours`.
- [x] Features em um único módulo `features.py`, compartilhado entre treino e inferência; janela de 12 amostras passadas.
- [x] Testes de causalidade e igualdade de features passaram.
- [x] Split por equipamento: **18 treino, 6 validação, 6 teste**, sem interseção.
- [x] MAE, RMSE, R², previsto versus real, importância e baseline exibidos no Treinamento.
- [x] Ambos venceram a média; a ativação só ocorre quando ambos são aceitos.
- [x] Treino novo foi ativado com a inferência em execução, sem reiniciar o container.
- [x] Previsões publicadas por RabbitMQ; regra persistiu/publicou o alerta.
- [x] Histerese: três previsões críticas para abrir e dez normais para resolver. Teste unitário e fluxo real passaram.
- [x] Insights mostra tendências de saúde, RUL e vibração, versão e alertas; o estado alimenta as cores do 3D.

### Métricas medidas novamente nesta auditoria

| Alvo | MAE teste | RMSE teste | R² teste | MAE baseline | RMSE baseline |
| --- | ---: | ---: | ---: | ---: | ---: |
| Saúde | 8,239 | 13,979 | 0,853 | 31,757 | 37,035 |
| RUL (horas) | 505,052 | 647,742 | 0,396 | 816,343 | 928,554 |

Dataset criado: `27a79a17` (prefixo observado na interface). Modelo ativo criado: `d69de0be-7254-4e8b-8d37-e45615f5088c`. Os artefatos antigos também permanecem.

**Limitação:** a RUL tem erro médio de aproximadamente 505 horas. Ela supera a baseline exigida, mas não deve ser apresentada como prazo preciso de falha real. Treino e simulação são sintéticos e não houve calibração em compressor físico. A janela de treino usa amostras em minutos e a demonstração ao vivo usa tempo acelerado; a generalização para dados físicos não foi validada.

## Assistente, segurança e infraestrutura

- [x] Ollama local no Compose, `llama3.2:3b`, execução CPU; sem API de LLM em nuvem no fluxo atual.
- [x] Backend monta resumo de leituras, previsões, alertas, métricas e arquitetura antes da pergunta.
- [x] LLM não acessa os bancos diretamente; recebe contexto pronto.
- [x] Resposta em streaming com status inicial “Carregando o modelo local…”.
- [x] Resposta renderizada como texto interpolado em Vue; sem `v-html`, HTML executável ou imagens remotas no chat.
- [x] Rate limit de cinco perguntas por minuto por usuário implementado; perguntas registradas em auditoria.
- [x] Download/aquecimento automático em `model-init`; terminou com zero.
- [x] Precisão dos valores/limites: os fatos são calculados pelo backend; o LLM seleciona apenas IDs de seções conhecidas e não pode introduzir uma comparação numérica livre na resposta. Testes cobriram saúde baixa com RUL normal, RUL baixa com saúde normal e recuperação por histerese, além de métricas/arquitetura.
- [x] Login JWT com viewer/operator/admin; acessos proibidos responderam 403 no teste de integração.
- [x] bcrypt no banco; limite de tentativas por IP e usuário implementado em `auth.py`.
- [x] Nenhum arquivo de segredos reais foi encontrado na lista de arquivos versionados; senhas geradas no volume, ignoradas pelo Git.
- [x] Mosquitto com senha/ACL e sem anônimo. Tentativa sem credencial foi rejeitada; simulação/gateway autenticados funcionaram.
- [x] WebSocket com ticket de 20 segundos e uso único; reutilização rejeitada.
- [x] Containers da aplicação sem root: API/gateway/Ollama UID 10001; frontend UID 101; outros workers usam a mesma imagem com USER court.
- [x] Porta 8080 para a aplicação; InfluxDB/RabbitMQ somente em 127.0.0.1; PostgreSQL não publica porta.
- [x] Links de InfluxDB, RabbitMQ e Swagger visíveis na aplicação. pgAdmin é exemplo opcional e não foi instalado.
- [x] Auditoria de login, comandos, jobs e cadastro consultada no PostgreSQL.
- [x] Healthchecks e dependências no Compose; serviços pontuais usam exit code zero em vez de healthcheck permanente.
- [x] Nove testes unitários passaram.
- [x] Novo build frontend **sem cache** passou: npm ci, vue-tsc e Vite; npm reportou zero vulnerabilidades na execução.

Os limites de login/chat foram conferidos no código; não foi executado um ensaio de bloqueio que deixasse os usuários reais sem acesso. O build informou chunks maiores que 500 kB: aviso de desempenho, não erro de compilação.

## Resolução das três pendências solicitadas

1. **Assistente corrigido.** Limites compartilhados entre regras e contexto; alertas novos descrevem saúde e RUL separadamente. Mensagens antigas genéricas não são usadas como prova dos limites atuais. Previsões vencidas/desligadas não fornecem valores como atuais. O Ollama recebe as seções factuais e retorna seus IDs por [saída estruturada](https://docs.ollama.com/capabilities/structured-outputs); somente o texto do backend é exibido, em streaming. O chat permanece local e continua selecionando informações a partir da pergunta em linguagem natural.
2. **README atualizado.** Diagrama AIoT completo e roteiro resumido incluídos diretamente na seção do segundo bimestre.
3. **GitHub publicado.** A revisão inclui as mudanças anteriores de organização, remoção do script de backup, hostname fixo do RabbitMQ, checklist, guia do notebook e correção do chat. Commit de código `ea229b8` enviado para a main e conferido com `git ls-remote`; este registro de conclusão acompanha a revisão.

Os **19 testes unitários** passaram. `python -m scripts.check_assistant` exercitou a rota e o Ollama real em quatro cenários controlados, em processo isolado: saúde 38/RUL 294,8; saúde 80/RUL 24; recuperação saúde 90/RUL 300 com alerta ainda ativo; métricas e arquitetura. Os valores, condições e streaming foram conferidos automaticamente. Os fixtures não modificam a telemetria nem o banco em uso.

O ensaio real `python -m scripts.check_live live` também passou após a correção: regra automática, inferência, falha, alerta persistido/WebSocket, chat em streaming e recuperação por histerese. Na resposta testada, o backend exibiu **saúde 36,80 abaixo de 40** e **RUL 277,93 h NÃO abaixo de 48 h**, apontando somente saúde como limite violado. Ao terminar, regra 16/10 °C restaurada e zero alertas ativos. Os 14 serviços permanentes ficaram saudáveis.

A inicialização do Ollama passou a consultar o modelo local antes de baixar; o teste de `model-init` mostrou “Modelo local existente; sem download.” e encerrou com código zero. Isso permite reutilizar o modelo preparado no notebook sem exigir novo download. O ensaio sem internet no próprio notebook continua pendente.

O notebook informado é Core i7 de 13ª geração, com 32 GB de RAM. O caminho recomendado é clonar o GitHub e preparar um ambiente novo antes da apresentação, conforme [o guia atualizado](apresentar-no-notebook.md). Contribuições de integrantes não foram alteradas nem inventadas.

### Registro histórico das pendências encontradas na auditoria inicial

Os itens abaixo descrevem o estado anterior à correção, não o status atual das três tarefas solicitadas.

1. **Assistente:** melhorar a descrição dos motivos do alerta e conferir a resposta contra os valores reais. Na tela de falha foram observados saúde próxima de 38 e RUL próxima de 294,8 h; a resposta do LLM afirmou que a RUL estava abaixo de 48 h. O texto genérico do alerta usa “saúde baixa ou vida útil abaixo de 48 h”; isso não prova que ambos os limites foram violados. Repetir perguntas sobre estado, falha, métricas e arquitetura após corrigir. Não tratar a resposta como diagnóstico confiável.
2. **README:** incluir diretamente na parte do segundo bimestre o diagrama AIoT atual e um roteiro resumido. O README já contém descrição, comando e nomes dos usuários e aponta ao roteiro completo, mas o diagrama embutido é o da versão original (ESP32 → MQTT → FastAPI → InfluxDB), na seção de referência. O diagrama atual está em `docs/implementacao-2bim.md`; é preciso levá-lo ao README para satisfazer literalmente o pedido.
3. **GitHub:** criar commit e publicar as mudanças locais. Nesta auditoria `git ls-remote origin refs/heads/main` confirmou o remoto em `6e2a551d0dab40d47c9ef39ae319586644194e91`; nenhum commit/push foi feito por esta verificação.
4. **Contribuições do grupo:** `git shortlog -sne HEAD` mostrou apenas RafaSMK (oito commits). O enunciado pede histórico de todos os integrantes. Se há mais integrantes, eles precisam registrar contribuições reais com as próprias contas; não inventar autoria. Nomes/tamanho do grupo não foram informados nesta conversa.
5. **Notebook/apresentação:** ensaiar a instalação, geração/treino e respostas do LLM no notebook escolhido; a validação deste PC não mede memória/desempenho dele. Seguir [apresentar-no-notebook.md](apresentar-no-notebook.md). No dia, mostrar a subida pelo Compose conforme o enunciado, além do acesso à interface.

### Diagrama enviado pelo usuário

O desenho é compatível com o fluxo geral, mas simplifica três aspectos da implementação: regras são um worker separado, gerador e treinador são consumidores distintos, e a API monta contexto para o LLM. PostgreSQL também guarda alertas, auditoria, jobs e versões; não apenas cadastros/regras. Para a apresentação, use o diagrama completo de `implementacao-2bim.md` e explique esses pontos.

## Checklist de ensaio presencial (16/11/2026)

- [ ] Subir a pilha com um comando e mostrar healthchecks/serviços de inicialização concluídos.
- [ ] Demonstrar visualizador, operador e administrador, incluindo uma ação negada.
- [ ] Mostrar simulador e mensagens MQTT/Mosquitto.
- [ ] Abrir Swagger/FastAPI.
- [ ] Mensageria: consumidores, taxas, fila acumulando com writer parado e drenando ao voltar; DLQ preservada.
- [ ] Mostrar leituras no InfluxDB e cadastro/regras/auditoria no PostgreSQL.
- [ ] Dashboard/WS, gráficos e consulta ao histórico.
- [ ] Refletores pela Web e refrigeração pela regra automática.
- [ ] Configurar e gerar pelo menos um milhão de leituras no Laboratório.
- [ ] Treinar os dois modelos e explicar métricas, split por equipamento e baseline.
- [ ] Injetar falha e mostrar saúde/RUL/alerta em Insights e 3D; desligar simulador e mostrar ausência de dados.
- [ ] Perguntar ao LLM sobre a falha e conferir a explicação com os valores da tela.
- [ ] Todos os integrantes capazes de explicar suas contribuições e a arquitetura.

## Efeitos da auditoria inicial, anterior à correção

Foram criados um dataset, uma nova versão de treino, um highlight e registros normais de auditoria. Duas mensagens inválidas de teste permanecem na DLQ. Um cadastro foi editado e restaurado. A regra foi restaurada, a falha foi resetada e writer/simulator foram retomados. Os refletores ficaram ligados pelo teste de comando, sem comando de desligamento posterior. Nenhum volume ou dado anterior foi apagado. Código funcional não foi alterado; somente esta checklist e sua referência no README foram acrescentadas nesta solicitação.
