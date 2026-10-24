"""Limites e fatos compartilhados entre regras e contexto do assistente."""
from datetime import datetime, timezone

HEALTH_LIMIT = 40
RUL_LIMIT_HOURS = 48
FRESH_SECONDS = 10


def limit_checks(prediction):
    upper = prediction.get('rul_interval', [None, prediction.get('rul_hours')])[1]
    return {
        'health_below_limit': prediction['health'] < HEALTH_LIMIT,
        'rul_below_limit': upper is not None and upper < RUL_LIMIT_HOURS,
    }


def measured_text(value, limit):
    # Não arredondar 39,999 para 40,00 e depois afirmar que está abaixo de 40.
    rounded = round(value, 2)
    return str(value) if (rounded < limit) != (value < limit) else f'{rounded:.2f}'


def prediction_facts(prediction):
    checks = limit_checks(prediction)
    health = measured_text(prediction['health'], HEALTH_LIMIT)
    health_state = 'ABAIXO' if checks['health_below_limit'] else 'NÃO abaixo'
    if prediction.get('rul_hours') is None:
        rul_text = 'RUL inconclusiva: não há prazo pontual confiável. ' + prediction.get('rul_reason', '')
    else:
        rul = measured_text(prediction['rul_hours'], RUL_LIMIT_HOURS)
        rul_state = 'ABAIXO' if checks['rul_below_limit'] else 'NÃO confirmado abaixo'
        # Compatibilidade com previsões sem faixa de erro.
        if 'rul_interval' not in prediction and not checks['rul_below_limit']:
            rul_state = 'NÃO abaixo'
        rul_text = f'RUL: {rul} horas, {rul_state} do limite {RUL_LIMIT_HOURS} horas.'
        if prediction.get('rul_status') == 'low_confidence':
            rul_text += ' Estimativa de BAIXA CONFIANÇA; o valor pontual não é um prazo confirmado.'
    if prediction.get('rul_interval'):
        low, high = prediction['rul_interval']
        rul_text += f' Faixa experimental: {low:.0f} a {high:.0f} horas; não é um prazo calibrado em equipamento real.'
        if checks['rul_below_limit']:
            rul_text += f' Toda a faixa está abaixo do limite de {RUL_LIMIT_HOURS} horas.'
    if prediction.get('rul_unit') == 'simulated_operating_hours':
        rul_text += ' Unidade: horas de operação simuladas, supondo continuidade da degradação atual; não são horas do relógio real.'
    return f'Saúde estimada: {health}/100, {health_state} do limite {HEALTH_LIMIT}. ' + rul_text


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
                        rul_unit=payload.get('rul_unit'), rul_status=payload.get('rul_status'),
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
