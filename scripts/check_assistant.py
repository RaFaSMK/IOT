"""Regressão do contexto do chat usando o Ollama real, sem alterar telemetria/bancos.

Executar dentro do container api. Os cenários e sessões mockadas existem somente
neste processo de teste; a rota e o streaming do assistente são os reais.
"""
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from sqlalchemy import select
import aiot.app as api
from aiot.database import Alert, ModelVersion, session


async def main():
    with session() as db:
        models = list(db.scalars(select(ModelVersion).order_by(ModelVersion.timestamp.desc())))
    active = [row for row in models if row.active]
    scenarios = [
        ('saude_apenas', 38., 294.8, True, 'Qual equipamento tem alerta e por quê? Cite saúde e RUL e diga quais limites estão realmente violados.'),
        ('rul_apenas', 80., 24., True, 'Qual equipamento tem alerta e por quê? Cite saúde e RUL e diga quais limites estão realmente violados.'),
        ('recuperacao', 90., 300., True, 'O compressor ainda tem alerta, mas recuperou as leituras. Explique saúde, RUL e por que o alerta ainda não desapareceu.'),
        ('metricas_arquitetura', 90., 300., False, 'Explique as métricas do treino ativo e como os dados passam pelo sistema. A RUL é precisa em um compressor real?'),
    ]
    for name, health, rul, alert_active, question in scenarios:
        now = datetime.now(timezone.utc)
        alert_rows = [Alert(id='qa:predictive', device_id='compressor_01', active=True,
                            message='Saúde baixa ou RUL abaixo de 48 horas.', timestamp=now)] if alert_active else []
        fake_db = MagicMock()
        fake_db.scalars.side_effect = lambda statement: alert_rows if statement.column_descriptions[0]['entity'] is Alert else active
        fake_db.scalar.return_value = models[0] if models else None
        fake_context = MagicMock()
        fake_context.__enter__.return_value = fake_db
        events = {'compressor_01': {'payload': {'status': 'ready', 'health': health, 'rul_hours': rul,
                                             'source_timestamp': now.isoformat(), 'version': 'qa'}}}
        with patch.object(api, 'session', return_value=fake_context), patch.object(api, 'audit'), \
                patch.object(api, 'predictions', events), patch.object(api, 'latest', {}):
            response = await api.assistant(api.ChatBody(question=question), {'username': 'qa_assistant', 'role': 'admin'})
            chunks, loading, done = [], False, False
            async for chunk in response.body_iterator:
                item = json.loads(chunk.strip()[6:])
                assert not item.get('error'), item
                loading = loading or item.get('status') == 'loading'
                done = done or item.get('done', False)
                if not item.get('status'):
                    chunks.append(item.get('text', ''))
            answer = ''.join(chunks).strip()
            assert loading and done and answer
            if name == 'saude_apenas':
                assert 'Saúde: 38.00/100, ABAIXO' in answer and 'RUL: 294.80 horas, NÃO abaixo' in answer, answer
            elif name == 'rul_apenas':
                assert 'Saúde: 80.00/100, NÃO abaixo' in answer and 'RUL: 24.00 horas, ABAIXO' in answer, answer
            elif name == 'recuperacao':
                assert 'Limites violados nesta previsão: nenhum.' in answer and 'dez previsões normais' in answer, answer
            else:
                assert 'MAE' in answer and 'RMSE' in answer and 'R²' in answer and 'RabbitMQ' in answer and 'não há calibração' in answer, answer
            print(json.dumps({'scenario': name, 'health': health, 'rul_hours': rul,
                              'alert_active': alert_active, 'answer': answer}, ensure_ascii=False), flush=True)
    print('Quatro respostas locais completas em streaming, com valores/limites/histerese e métricas conferidos: OK.', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
