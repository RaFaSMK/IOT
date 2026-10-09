# Contexto para retomar o projeto após formatar o PC

Este arquivo registra o contexto da implementação com o Codex. Ele permite continuar em uma conversa nova, sem depender do histórico deste chat.

## Pedido e decisões do usuário

- Evoluir o projeto do primeiro bimestre conforme o enunciado `2Bim.MD`, para apresentação em **16/11/2026**.
- Manter a quadra inteligente de beach tennis e os highlights.
- Fazer o necessário para os requisitos, sem acrescentar funcionalidades desnecessárias.
- Usar temperatura ambiente, umidade e luminosidade. O usuário considerou inadequada a proposta inicial de ventilador.
- Usar refletores controlados pela Web e refrigeração de um bebedouro como os dois atuadores. O compressor do bebedouro é o equipamento para manutenção preditiva, medido por temperatura, corrente e vibração.
- Preparar este Markdown na pasta do projeto e enviar a implementação ao GitHub.
- Após verificar o backup dos dados em `D:\Backups\IOT`, remover os containers, imagens e volumes deste projeto, fechar o Docker e desligar o PC normalmente.

O documento da atividade contém requisitos acadêmicos e exemplos. Exemplos como ventiladores e bombas não são obrigações de usar esses dispositivos. Não há captura real de vídeo nem recomendação individual de consumo de água.

## Projeto

- Pasta original: `D:\Projetos\IOT`.
- Repositório: <https://github.com/RaFaSMK/IOT>.
- Branch original: `main`.
- Base anterior: `48feb16`, com Wokwi/Python para botão de highlight, MQTT, FastAPI, InfluxDB e Vue/ECharts.
- Nova entrada da API: `backend/aiot/app.py`; nova interface: `frontend/src/views/CourtApp.vue`.
- O código do primeiro bimestre permanece como referência. O Compose usa a nova versão AIoT.

## Implementação

Tecnologias: Vue 3, TypeScript, Vite, ECharts, Three.js, FastAPI, WebSocket, Mosquitto, RabbitMQ, PostgreSQL, InfluxDB, NumPy/scikit-learn e Ollama local com `llama3.2:3b`.

Fluxos:

1. Simulador Python → MQTT → gateway → RabbitMQ → gravação no InfluxDB, regras, inferência e API → WebSocket → dashboard/3D.
2. Botão Web → API → RabbitMQ → gateway → MQTT → simulador → confirmação e estado nas próximas leituras.
3. Laboratório → job RabbitMQ → dataset → treino em outra fila → artefato versionado → inferência em tempo real → previsões e alertas RabbitMQ → interface.
4. Pergunta → API monta resumo de dados, alertas e métricas → Ollama local → resposta em streaming. O LLM não acessa os bancos diretamente.

Sensores: `ambient_temperature`, `humidity`, `luminosity`, `water_temperature`, `compressor_temperature`, `compressor_current`, `compressor_vibration`.

Outros dispositivos: `compressor_01`, `cooling`, `floodlights`, `highlight_button`, `simulator`. IDs são compartilhados entre cadastro e 3D; posições ficam apenas no frontend.

Refrigeração automática: liga acima de 16 °C e desliga abaixo de 10 °C, com limites editáveis pelo administrador. Falha injetada aumenta progressivamente as medições do compressor; reset restaura o equipamento. O simulador publica a cada dois segundos e aceita pausa/retomada.

RabbitMQ: exchange topic `court.events`, exchange de descarte `court.dead`, filas `court.api`, `court.writer`, `court.inference`, `court.rules`, `court.gateway`, `court.generator`, `court.trainer` e `court.dlq`. Credenciais e permissões próprias por serviço. Mensageria consulta a API administrativa pelo backend; inspeção da DLQ mantém mensagens.

PostgreSQL: usuários, dispositivos, regras, alertas, auditoria, jobs e versões. InfluxDB: histórico dos sensores e highlights. Volume de artefatos: datasets e modelos.

## Dados e IA

- Configuração padrão gera 1.555.200 leituras, em 518.400 amostras: 30 equipamentos × 60 dias, intervalo de cinco minutos, três tipos de sensores.
- Geração vetorizada por equipamento, memmap e teto de dois milhões de amostras/vinte milhões de leituras.
- Ruído, ausências, outliers, ciclos diários/sazonais, falhas progressivas e semente configuráveis.
- Saúde e RUL são rótulos exclusivos do dataset; não são enviados na telemetria ao vivo.
- `backend/aiot/features.py` é compartilhado por treino e inferência: janela de 12 medições passadas, última leitura, média, desvio, máximo e tendência de cada canal.
- Split por equipamento: 60% treino, 20% validação, 20% teste. Até 50 mil amostras em cada conjunto para ajuste/avaliação.
- Dois ExtraTreesRegressor: saúde 0–100 e RUL em horas. MAE, RMSE, R², baseline da média, scatter e importância dos atributos.
- A versão só é ativada se ambos vencerem a baseline. Troca atômica e recarregamento sem reiniciar a inferência.
- Alertas: três previsões seguidas com saúde < 40 ou RUL < 48 h para abrir; dez previsões fora desses limites para resolver. Persistência no PostgreSQL.
- Estimativas demonstram o cenário sintético; não foram calibradas em um compressor real.

## Interface e segurança

Dashboard, highlights, quadra 3D, cadastro, Mensageria, Laboratório, Treinamento, Insights, Assistente e Administração.

3D só usa dados recebidos pelo WebSocket. Luminosidade modifica iluminação; umidade modifica nuvens; refletores acendem e compressor gira/treme conforme estado e vibração. Sem telemetria recente por dez segundos, indica ausência e pausa animações dos dispositivos. Painel por item com leitura, gráfico, saúde e comandos.

Login JWT: `visualizador` lê, `operador` comanda, `administrador` também gerencia, gera, treina e consulta auditoria. Senhas aleatórias geradas no bootstrap; banco armazena bcrypt. Limites de login e chat. WebSocket recebe ticket curto de uso único, sem JWT na URL. Aplicações em containers sem root. Frontend na porta 8080; gerenciamento RabbitMQ e InfluxDB só em 127.0.0.1. Segredos, dados locais e artefatos estão ignorados pelo Git.

## Executar depois da formatação

1. Instalar Git e Docker Desktop com WSL2. Disponibilizar ao Docker ao menos 8 GB, conforme o enunciado.
2. Recuperar a pasta do projeto ou clonar o GitHub.
3. Na raiz, executar `docker compose up --build -d`.
4. Aguardar `docker compose ps` mostrar os serviços saudáveis. O primeiro preparo baixa imagens e o modelo local.
5. Abrir <http://localhost:8080>.
6. Consultar as senhas locais: `docker compose run --rm --no-deps bootstrap cat /secrets/demo-users.txt`.
7. Seguir [o roteiro completo](docs/implementacao-2bim.md).

Sem restaurar volumes, o Compose cria um ambiente novo. O laboratório permite gerar e treinar novamente. O histórico, contas e artefatos anteriores dependem do backup dos volumes; instruções acompanham o backup em D:.

Dependências para desenvolvimento: Python com `uv` no backend e Node para compilar o frontend; Node não é backend. Para subir pelos containers, basta Docker. Dependências Python estão fixadas em `uv.lock`/`requirements.lock.txt`; frontend usa `package-lock.json`.

## Verificações

- Nove testes unitários passaram: efeitos dos atuadores/falha, volume mínimo, histerese, contrato de mensagens, ausência de rótulos na telemetria e features causais compartilhadas.
- Build Vue/TypeScript passou; auditoria npm retornou zero vulnerabilidades na verificação.
- Geração e treino locais reais foram executados com 1.555.200 leituras. Saúde: MAE 8,239, RMSE 13,979, R² 0,853; baseline MAE 31,756. RUL: MAE 505,0 h, RMSE 647,742 h, R² 0,396; baseline MAE 816,0 h. Ambos superaram a baseline; RUL ainda tem erro considerável.
- Integração em Docker e inspeção visual: resultados finais serão registrados em `docs/validacao-2bim.md`.

Comandos de teste:

```powershell
cd backend
uv sync
uv run python -m unittest discover -s tests -v
cd ../frontend
npm ci
npm run build
cd ..
docker compose exec api python -m scripts.check_integration
docker compose exec api python -m scripts.check_live dlq
docker compose exec api python -m scripts.check_live live
```

Para mostrar fila acumulando: `docker compose stop writer`, abrir Mensageria e depois `docker compose start writer`.

## Recuperar o contexto no Codex

Após reinstalar e abrir o projeto, pode iniciar uma conversa nova com:

> Leia CONTEXTO_PARA_RETOMAR.md, docs/implementacao-2bim.md, docs/validacao-2bim.md e o enunciado docs/2Bim.MD. Analise o estado atual do código e continue a preparação da atividade do segundo bimestre. Mantenha a quadra, highlights, sensores, refletores e compressor do bebedouro. Não acrescente funcionalidades fora do enunciado. Considere as verificações e limitações registradas.

Este arquivo preserva as decisões e o estado técnico, não uma transcrição integral da conversa. Para preservar transcrições locais, salve também `C:\Users\wagne\.codex\sessions` e, se necessário, `archived_sessions`, em uma unidade preservada. A documentação oficial identifica esses diretórios como locais das transcrições: [Troubleshooting](https://learn.chatgpt.com/docs/reference/troubleshooting#feedback-and-logs). Não dependa apenas de reinstalar ou entrar na conta para recuperar arquivos locais.

## Incidente com Docker após queda de energia

Docker Desktop apresentou erros de sockets Windows em `AppData\Local\Docker\run\dockerInference` e `AppData\Local\docker-secrets-engine\engine.sock`. Foram encerrados os processos Docker e apenas a distribuição WSL `docker-desktop`; diretórios de sockets temporários foram renomeados para backup. Não houve reset nem exclusão de dados nessa recuperação. Docker voltou a responder. A montagem inicial das imagens apresentou forte espera de disco; os serviços Python agora compartilham uma imagem para evitar montagens repetidas.

Histórico dos integrantes deve refletir contribuições reais. Não inventar autores, commits, métricas ou verificações que não foram executadas.
