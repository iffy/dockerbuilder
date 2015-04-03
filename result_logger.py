import pika
import argparse
import json
from structlog import get_logger

from simplebuilder.common import makeTemporaryStatusQueue
from simplebuilder.common import declareThings, add_rabbit_host_arg

log = get_logger()

def callback(ch, method, properties, body):
    data = json.loads(body)
    log.info(key=method.routing_key, req_id=properties.correlation_id, **data)


def startPrinting(rabbit_host):
    log.info('connecting to rabbit', host=rabbit_host)
    parameters = pika.ConnectionParameters(rabbit_host)
    conn = pika.BlockingConnection(parameters)
    channel = conn.channel()
    declareThings(channel)
    queue = makeTemporaryStatusQueue(channel)

    channel.basic_consume(callback,
        queue=queue,
        no_ack=True)
    channel.start_consuming()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Connect an build a request')
    add_rabbit_host_arg(parser)
    
    args = parser.parse_args()
    startPrinting(args.rabbit_host)
