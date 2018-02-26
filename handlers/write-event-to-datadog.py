'''Write an ASG scaling event to Datadog'''

import datadog
import logging
import iso8601
import json
import os

log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.root.setLevel(logging.getLevelName(log_level))
_logger = logging.getLogger(__name__)

DATADOG_API_KEY = os.environ.get('DATADOG_API_KEY')
DATADOG_APP_KEY = os.environ.get('DATADOG_APP_KEY')
datadog.initialize(api_key=DATADOG_API_KEY, app_key=DATADOG_APP_KEY)

SOURCE_TYPE_NAME = 'AWS/ASG'

def _create_datadog_event(event: dict) -> dict:
    datadog_event = {}

    event_name = event.get('detail').get('eventName')
    table_name = event.get('detail').get('requestParameters').get('tableName')
    region = event.get('region')
    event_title = 'DynamoDB Auto Scaling {event_name}: {table_name}'.format(
        event_name=event_name,
        table_name=table_name
    )

    wcu_resize = _get_resize(event.get('detail'), 'writeCapacityUnits')
    rcu_resize = _get_resize(event.get('detail'), 'readCapacityUnits')

    datadog_event['title'] = event_title
    datadog_event['date_happened'] = int(iso8601.parse_date(event.get('time')).timestamp())
    datadog_event['source_type_name'] = SOURCE_TYPE_NAME
    datadog_event['host'] = table_name
    datadog_event['alert_type'] = 'info'

    datadog_event['text'] = _get_event_text(
        dynamodb_table=table_name,
        region=region,
        rcu_resize=rcu_resize,
        wcu_resize=wcu_resize
    )

    return datadog_event


def _get_event_text(dynamodb_table: str, region: str, rcu_resize: tuple, wcu_resize: tuple) -> str:
    '''Return a formatted event message'''
    msg = '''
    DynamoDB Table {ddt}
    Region: {region}

    RCU: {rcu}
    WCU: {wcu}
    '''

    if rcu_resize[0] == rcu_resize[1]:
        rcu = 'Unchanced : {}'.format(rcu_resize[0])
    elif rcu_resize[0] < rcu_resize[1]:
        rcu = 'Up: {}'.format(' -> '.join(rcu_resize))
    elif rcu_resize[0] > rcu_resize[1]:
        rcu = 'Down: {}'.format(' -> '.join(rcu_resize))

    if wcu_resize[0] == wcu_resize[1]:
        wcu = 'Unchanced : {}'.format(wcu_resize[0])
    elif wcu_resize[0] < wcu_resize[1]:
        wcu = 'Up: {}'.format(' -> '.join(wcu_resize))
    elif wcu_resize[0] > wcu_resize[1]:
        wcu = 'Down: {}'.format(' -> '.join(wcu_resize))

    return msg.format(ddt=dynamodb_table, region=region, rcu=rcu, wcu=wcu)


def _get_resize(event_detail: dict, unit_type: str) -> tuple:
    '''Return the change in RCUs'''
    current = event_detail.get('responseElements').get('tableDescription').get('provisionedThroughput').get(unit_type)
    new = event_detail.get('requestParameters').get('provisionedThroughput').get(unit_type)

    return (current, new)

def handler(event, context):
    '''Function entry.'''
    _logger.info('Event received: {}'.format(json.dumps(event)))

    datadog_event = _create_datadog_event(event)
    resp = datadog.api.Event.create(**datadog_event)

    _logger.info(json.dumps(resp))
    return json.dumps(resp)


