# Apresentar no notebook

O caminho recomendado é **clonar o GitHub e preparar um ambiente novo no notebook**, com antecedência e internet. O notebook informado tem **Core i7 de 13ª geração e 32 GB de RAM**, uma boa margem para a pilha em CPU. O tempo real de geração, treino e resposta do Ollama deve ser medido nele.

O código não inclui os volumes Docker: o notebook terá contas e senhas novas, histórico novo e precisará gerar/treinar seus modelos. Os dados atuais continuam no Docker deste PC.

## 1. Preparar o notebook com antecedência e internet

Instale Git e o [Docker Desktop para Windows](https://docs.docker.com/desktop/setup/install/windows-install/) com mecanismo WSL2 e containers Linux. Se o WSL ainda não estiver instalado, execute no PowerShell como administrador:

```powershell
wsl --install --no-distribution
```

Reinicie se solicitado, execute `wsl --update` e abra o Docker Desktop. Confira `docker info` e `docker compose version`.

O projeto pede pelo menos 8 GB disponíveis para o Docker, além da memória usada pelo Windows. Com 32 GB totais há margem; se você tiver limitado manualmente o WSL, deixe pelo menos 8 GB, preferindo 12–16 GB para geração/treino e Ollama juntos. GPU não é obrigatória: o Ollama funciona na CPU. Reserve espaço para imagens, modelo local, bancos e datasets. Python, Node, Mosquitto, RabbitMQ, PostgreSQL, InfluxDB e Ollama são fornecidos pelos containers.

## 2. Baixar o projeto do GitHub

No PowerShell comum do notebook:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Projetos" | Out-Null
cd "$env:USERPROFILE\Projetos"
git clone https://github.com/RaFaSMK/IOT.git
cd IOT
```

Se a pasta já existir por um clone anterior, entre nela e use `git pull --ff-only`, conferindo antes se há alterações locais com `git status`. Não clone por cima de uma pasta existente.

Com o Docker Desktop aberto, na pasta do projeto:

```powershell
docker compose up --build -d
docker compose ps -a
```

A primeira execução precisa de internet para baixar imagens, dependências e `llama3.2:3b`. Aguarde os serviços permanentes saudáveis; `bootstrap`, `database-init` e `model-init` devem terminar com `Exited (0)`. Confira o preparo do modelo com `docker compose logs --tail 30 model-init`.

## 3. Acessar e preparar os modelos

Abra <http://localhost:8080>. Consulte as senhas no terminal, dentro da pasta do projeto:

```powershell
docker compose run --rm --no-deps bootstrap cat /secrets/demo-users.txt
```

Entre como `administrador`. No **Laboratório**, gere o dataset padrão e aguarde a conclusão. Em **Treinamento**, selecione esse dataset, execute o treino e confira que terminou e que a versão foi ativada. Sem uma versão ativa, não haverá as previsões treinadas do compressor. Faça essa etapa antes do dia da apresentação; geração, treino e respostas do LLM dependem do desempenho do notebook.

O padrão atual gera 5.184.000 leituras de 100 equipamentos. A nova dinâmica não usa os datasets antigos: preserve-os como histórico e gere um novo dataset para treinar. A RUL aparece em horas de operação simuladas; em condição saudável fica inconclusiva e durante a falha pode só ganhar prazo pontual na fase final. Consulte [a validação v2](validacao-rul-v2-2026-10-20.md).

Confira Dashboard, quadra 3D, highlights, Mensageria, Treinamento e Assistente. Verifique que as leituras mudam e que há previsões. Teste os refletores, a falha do compressor e o reset conforme [o roteiro completo](implementacao-2bim.md). Apresente as métricas obtidas no próprio notebook.

Para conferir os testes Python:

```powershell
docker compose exec api python -m unittest discover -s tests -v
```

Para um ensaio automático da regra, falha, alerta, Assistente e recuperação, depois de treinar:

```powershell
docker compose exec api python -m scripts.check_live live
```

Esse ensaio cria comandos e registros de auditoria, injeta falha e depois restaura a regra/reset do compressor. Não execute ao mesmo tempo que estiver demonstrando controles manualmente. O teste pode levar alguns minutos, especialmente enquanto o LLM responde.

## 4. Ensaiar sem internet

Depois de baixar tudo e concluir geração/treino, execute `docker compose stop`. Desconecte a internet e reabra os serviços já criados:

```powershell
cd "$env:USERPROFILE\Projetos\IOT"
docker compose start
docker compose ps -a
```

Abra a interface e teste as previsões e o Assistente. `start` reutiliza containers, imagens e volumes já preparados; não é necessário refazer build. Os serviços de inicialização podem executar novamente, mas `model-init` verifica primeiro o modelo local e só tenta baixá-lo se estiver ausente. Faça esse ensaio real no notebook para confirmar que a apresentação funciona offline.

## 5. No dia

Conecte o notebook à tomada, abra o Docker Desktop, aguarde o mecanismo iniciar e execute na pasta do projeto:

```powershell
cd "$env:USERPROFILE\Projetos\IOT"
docker compose start
docker compose ps -a
```

Abra <http://localhost:8080> e siga [o roteiro de demonstração](implementacao-2bim.md#demonstração-na-ordem-do-enunciado). Para demonstrar a subida pelo Compose com tudo já preparado, use `docker compose up -d --pull never --no-build`; o modelo já baixado é reutilizado. A primeira preparação com internet continua sendo `docker compose up --build -d`. Desative a suspensão automática durante a apresentação. Ao terminar, use `docker compose stop`.

Se atualizar o código depois da preparação, execute `git pull --ff-only` e `docker compose up --build -d`, seguido de `docker compose restart frontend` para atualizar a conexão do proxy com uma API recriada. Repita os testes antes da apresentação.

Não use `docker compose down -v`: esse comando apaga os volumes e exigiria preparar novamente os dados e modelos.

## Se quiser levar exatamente o estado deste PC

Copiar somente o código não leva histórico, senhas e modelo treinado. Para manter exatamente esse estado, será necessário exportar os volumes do PC, com os serviços parados, e importá-los no notebook antes de iniciá-lo pela primeira vez. Os backups antigos foram apagados a pedido; uma eventual transferência precisa ser criada a partir dos volumes atuais. Este roteiro prepara os modelos diretamente no notebook.
