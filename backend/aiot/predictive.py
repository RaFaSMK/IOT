"""Limites e fatos compartilhados entre regras e contexto do assistente."""
from datetime import datetime, timezone

HEALTH_LIMIT = 40
RUL_LIMIT_HOURS = 48
FRESH_SECONDS = 10


def limit_checks(prediction):
    return {
        'health_below_limit': prediction['health'] < HEALTH_LIMIT,
        'rul_below_limit': prediction['rul_hours'] < RUL_LIMIT_HOURS,
    }


def measured_text(value, limit):
    # Não arredondar 39,999 para 40,00 e depois afirmar que está abaixo de 40.
    rounded = round(value, 2)
    return str(value) if (rounded < limit) != (value < limit) else f'{rounded:.2f}'


def prediction_facts(prediction):
    checks = limit_checks(prediction)
    health = measured_text(prediction['health'], HEALTH_LIMIT)
    rul = measured_text(prediction['rul_hours'], RUL_LIMIT_HOURS)
    health_state = 'ABAIXO' if checks['health_below_limit'] else 'NÃO abaixo'
    rul_state = 'ABAIXO' if checks['rul_below_limit'] else 'NÃO abaixo'
    return (f'Saúde: {health}/100, {health_state} do limite {HEALTH_LIMIT}. '
            f'RUL: {rul} horas, {rul_state} do limite {RUL_LIMIT_HOURS} horas.')


def assistant_predictions(events, alerts, now=None):
    now = now or datetime.now(timezone.utc)
    result = {}
    for identifier, event in events.items():
        payload = event['payload']
        timestamp = payload.get('source_timestamp')
        try:
            observed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            age = (now - observed).total_seconds()
            fresh = 0 <= age < FRESH_SECONDS
        except (AttributeError, TypeError, ValueError):
            fresh = False
        item = {'status': payload.get('status'), 'version': payload.get('version'),
                'source_timestamp': timestamp, 'fresh': fresh}
        if payload.get('status') == 'ready' and fresh:
            item.update(health=payload['health'], rul_hours=payload['rul_hours'],
                        limit_checks=limit_checks(payload), facts=prediction_facts(payload))
        else:
            item['facts'] = 'Não há previsão recente disponível; não afirmar valores ou limites atuais.'
        active = any(row['device_id'] == identifier and row.get('active', True) for row in alerts)
        item['alert_active'] = active
        item['alert_state'] = ('Alerta persistido ativo. Pode continuar ativo durante a recuperação: '
                               'são necessárias dez previsões normais consecutivas para resolver.' if active else
                               'Sem alerta persistido ativo. São necessárias três previsões críticas consecutivas para abrir.')
        result[identifier] = item
    return result
