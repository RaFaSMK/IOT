# Exibição da RUL — 23/10/2026

> Continuação no mesmo dia: as [temperaturas passaram a responder de forma gradual](validacao-temperaturas-2026-10-23.md). O modelo mantido foi reavaliado nesse perfil; os resultados abaixo registram a execução anterior ao ajuste térmico.

O usuário pediu para ver também estimativas menos confiáveis durante a
apresentação. O modelo ativo e o dataset não mudaram. Não houve novo treino:
mudou a política de exibição da previsão e sua identificação na interface.

## Regra atual

- Sem modelo, sem telemetria recente, durante a janela inicial ou com compressor
  desligado: previsão indisponível, sem preencher o gráfico com dados antigos.
- Saúde estimada >= 90/100: **Sem prazo identificado**. O modelo foi treinado
  para estimar RUL na degradação; a saída bruta nessa região saudável seria uma
  extrapolação, sem prazo identificável. Não é apenas uma estimativa menos precisa.
- Saúde < 90/100, janela completa e modelo com calibração: publicar a estimativa
  de RUL e a faixa experimental, mesmo quando o erro de validação é amplo.
- Se o raio de erro exceder o maior entre 0,5 h e 25% da estimativa, marcar
  **Baixa confiança**, acrescentar `≈` ao número e explicar a faixa. Antes,
  esse critério ocultava o prazo; agora só muda sua qualificação.
- O gráfico da RUL é tracejado e identificado como experimental. Inclui as
  estimativas de baixa confiança; mantém lacunas nos períodos indisponíveis ou
  sem degradação suficiente. O 3D e o assistente também informam baixa confiança.

O alerta continua usando o extremo superior da faixa para comparar a RUL com
o limite de 48 h. Um valor pontual baixo com faixa ultrapassando esse limite
não confirma sozinho a violação. Limites de saúde e histerese não mudaram.

As horas continuam sendo **horas de operação simuladas**, não horas do relógio
real. A faixa é empírica e não tem garantia de cobertura de 90%. Esta mudança
não melhora a precisão do regressor nem constitui calibração em equipamento real.

## Verificações

- 34 testes Python aprovados, incluindo publicação de estimativa com erro amplo,
  fronteiras do indicador de confiança, ausência de prazo saudável e prevenção
  de alerta indevido quando somente o ponto está abaixo do limite.
- Build Vue/TypeScript aprovado (permanece o aviso de tamanho do bundle).
- Três cenários saudáveis e seis cenários de falha passaram com o modelo ativo
  `e6d27772-bdb9-49d1-b74c-1fa84e6e1843`.
- Ensaio integrado real aprovado: condição saudável sem prazo indevido, regra
  automática, falha, alerta persistido/WS, oito valores de RUL (4,797 → 3,962 h),
  assistente local em streaming e recuperação com limpeza do alerta. O bloco
  final restaurou o equipamento e a configuração original da regra.
- Interface conferida no navegador: `≈ 2,6 h simuladas`, indicador **Baixa
  confiança**, faixa de 1,5 a 3,6 h e gráfico tracejado durante a falha. Após
  recuperação: saúde 99/100 e **Sem prazo identificado**. Console sem erros.
- Nas três sementes adicionais do ensaio anterior:

| Cenário | Valores publicados antes → agora | Baixa confiança agora | Primeiro → último valor |
|---|---:|---:|---:|
| Rolamento, seed 13579 | 12 → 61 | 49 | 5,646 → 0,265 h |
| Superaquecimento, seed 24680 | 15 → 102 | 87 | 5,591 → 0,119 h |
| Desbalanceamento, seed 97531 | 9 → 38 | 29 | 4,128 → 0,208 h |

São cenários sintéticos de avaliação, não garantias para toda execução. Os
valores podem oscilar com as medições; não foi imposta uma contagem regressiva.

As pendências de ensaio offline, fila acumulando/drenando e preparação da máquina
da apresentação continuam descritas na [validação v2](validacao-rul-v2-2026-10-20.md).
