import json
import time
import os
import uuid
import pika

BUILD_STATUS_EXCHANGE = 'build_status_x'
BUILD_REQUEST_QUEUE = 'build_request_q'
BUILD_FINISH_QUEUE = 'build_finish_q'

def add_rabbit_host_arg(parser):
    parser.add_argument('--rabbit-host', '-H',
        default=os.environ.get('RABBIT_HOST', '127.0.0.1'),
        help='RabbitMQ host (default %(default)s) also you can set RABBIT_HOST env')


def declareThings(channel):
    """
    I set up the build status exchange and the build request queue
    and build finish queue.
    """
    channel.queue_declare(queue=BUILD_REQUEST_QUEUE)
    channel.queue_declare(queue=BUILD_FINISH_QUEUE)

    channel.exchange_declare(
        exchange=BUILD_STATUS_EXCHANGE,
        type='topic')

    channel.queue_bind(
        exchange=BUILD_STATUS_EXCHANGE,
        queue=BUILD_REQUEST_QUEUE,
        routing_key='build.request')

    channel.queue_bind(
        exchange=BUILD_STATUS_EXCHANGE,
        queue=BUILD_FINISH_QUEUE,
        routing_key='build.finish')


def makeTemporaryStatusQueue(channel):
    """
    Return a queue name that will receive build status updates from now
    on (until this process dies).
    """
    result = channel.queue_declare(exclusive=True)
    channel.queue_bind(
        exchange=BUILD_STATUS_EXCHANGE,
        queue=result.method.queue,
        routing_key='build.*')
    return result.method.queue


def makePermanentStatusQueue(channel, name):
    """
    Make a queue that will receive build results from now on
    AND will not go away when this process dies.
    """
    result = channel.queue_declare(name)
    channel.queue_bind(
        exchange=BUILD_STATUS_EXCHANGE,
        queue=result.method.queue,
        routing_key='build.*')
    return result.method.queue    


def makeBuildRequest(channel, name, clone_url, revision, steps, timeout):
    """
    Steps is a list of dicts with these keys:

        - args - list of command line argument strings
        - env - dictionary of environment vars
        - workdir - relative directory to run the command in
        - timeout - number of seconds this step is allowed to run
    """
    message = json.dumps({
        'version': '1',
        'name': name,
        'created_time': time.time(),
        'clone_url': clone_url,
        'revision': revision,
        'steps': steps,
        'timeout': timeout,
    })
    channel.basic_publish(
        exchange=BUILD_STATUS_EXCHANGE,
        routing_key='build.request',
        body=message,
        properties=pika.BasicProperties(
            correlation_id=str(uuid.uuid4()),
        ),
    )


def _sendResult(channel, method, props, body, log):
    channel.basic_publish(
        exchange=BUILD_STATUS_EXCHANGE,
        routing_key='build.finish',
        body=json.dumps(body),
        properties=props,
    )
    log.info('result sent')
    channel.basic_ack(delivery_tag=method.delivery_tag)
    log.info('ack sent')


def sendBuildSuccess(channel, method, props, result, log):
    _sendResult(channel, method, props, {
        'success': True,
        'result': result,
        'end_time': time.time(),
    }, log)


def sendBuildFailure(channel, method, props, error, error_data, log):
    _sendResult(channel, method, props, {
        'success': False,
        'error': str(error),
        'error_data': error_data,
        'end_time': time.time(),
    }, log)


def sendBuildStatus(channel, props, data):
    channel.basic_publish(
        exchange=BUILD_STATUS_EXCHANGE,
        routing_key='build.status',
        body=json.dumps(data),
        properties=props,
    )

