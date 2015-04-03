"""
I connect to RabbitMQ and run whatever scripts are in there.

Don't run me on machines you value or if you don't trust the requests in RabbitMQ.
"""

import pika
import argparse
import json
import uuid
import time
import tempfile
from structlog import get_logger

from twisted.python.filepath import FilePath
from twisted.internet import protocol, defer, task

from simplebuilder.common import sendBuildSuccess, sendBuildFailure, declareThings
from simplebuilder.common import add_rabbit_host_arg, BUILD_REQUEST_QUEUE
from simplebuilder.common import sendBuildStatus

class TimeoutProcessProtocol(protocol.ProcessProtocol):

    def __init__(self, reactor, timeout=(20 * 60), log=None, channel=None, properties=None, name=None):
        self.timeout = timeout or (20*60)
        self.reactor = reactor
        self.done = defer.Deferred()
        self.log = log
        if not log:
            self.log = get_logger()
        self.stdout = ''
        self.stderr = ''
        self.channel = channel
        self.properties = properties
        self.name = name


    def _sendEvent(self, event, **data):
        data.update({
            'event': event,
            'pname': self.name,
            'time': time.time(),
        })
        sendBuildStatus(self.channel, self.properties, data)

    def connectionMade(self):
        self._starttime = time.time()
        self.cancel_call = self.reactor.callLater(self.timeout, self.cancel, 'timeout')
        self._sendEvent('process_started')
        

    def cancel(self, reason):
        self.log.info('sending KILL', reason=reason)
        self.transport.signalProcess('KILL')
        self._sendEvent('cancel', reason=reason)

    def outReceived(self, data):
        self.log.msg('stdout', data=data)
        self._sendEvent('stdout', data=data)

    def errReceived(self, data):
        self.log.msg('stderr', data=data)
        self._sendEvent('stderr', data=data)

    def processEnded(self, reason):
        runtime = time.time() - self._starttime
        if self.cancel_call and not self.cancel_call.called:
            self.cancel_call.cancel()

        code = reason.value.status
        self._sendEvent('process_ended', rc=code, runtime=runtime)
        if code:
            self.log.error('process failed', exc_info=reason)
            self.done.errback(reason)
        else:
            self.log.msg('process succeeded')
            self.done.callback(code)



def startBuilding(reactor, rabbit_host, timeout):
    log = get_logger()
    log.info('connecting to rabbit', host=rabbit_host)
    parameters = pika.ConnectionParameters(rabbit_host)
    conn = pika.BlockingConnection(parameters)
    channel = conn.channel()
    declareThings(channel)

    builder = Builder(reactor, timeout, log)
    consumer = QueueConsumer(channel, BUILD_REQUEST_QUEUE,
        builder.buildMessage)
    consumer.start()
    return defer.Deferred()


class Builder(object):
    """
    I run the processes I'm told to run...

        ...kind of like remote code execution...
    """

    workdir = 'work'

    def __init__(self, reactor, timeout, log):
        self.reactor = reactor
        self.timeout = timeout
        self.log = log


    @defer.inlineCallbacks
    def buildMessage(self, channel, method, properties, body):
        log = self.log
        log = log.bind(message_id=str(uuid.uuid4()))
        data = None
        try:
            data = json.loads(body)
        except Exception as e:
            log.error(exc_info=e)
            sendBuildFailure(channel, method, properties, str(e), body, log)
            return

        # setup
        tmpdir = FilePath(tempfile.mkdtemp(prefix='simplebuilder-'))

        try:
            results = []
            log.msg(number_of_steps=len(data['steps']))
            for step in data['steps']:
                step_start = time.time()
                rc = yield self._build(
                    step, tmpdir, data.get('timeout', self.timeout), log,
                    channel, properties)
                results.append({
                    'rc': rc,
                    'start': step_start,
                    'end': time.time(),
                })
            log.info('done building')
            sendBuildSuccess(channel, method, properties, results, log)
        except Exception as e:
            print 'Exception?', e
            log.info(exc_info=e)
            sendBuildFailure(channel, method, properties, str(e), None, log)
        yield self.tearDown(tmpdir, log)


    def tearDown(self, tmpdir, log):
        log.info('destroying temporary dir', rootpath=tmpdir.path)
        tmpdir.remove()


    def _run(self, args, env, path, timeout, log, channel, properties):
        name = ' '.join(args)
        pp = TimeoutProcessProtocol(reactor=self.reactor,
            timeout=timeout,
            log=log,
            channel=channel,
            properties=properties,
            name=name)
        log.info('spawn', args=args, env=env, path=path)
        self.reactor.spawnProcess(pp, args[0], args, env=env, path=path)
        return pp.done


    def _build(self, step_data, rootpath, build_timeout, log, channel, properties):
        log.info('building', step_data=step_data, root=rootpath.path)
        env = {}
        #os.environ.copy()
        env.update(step_data.get('env', {}))
        args = step_data['args']
        workdir = rootpath
        for segment in step_data.get('workdir', '').split('/'):
            workdir = workdir.child(segment)
        timeout = min([
            self.timeout,
            step_data.get('timeout', self.timeout),
            build_timeout,
        ])
        log.info('timeout chosen', timeout=timeout)
        return self._run(args, env, workdir.path, timeout, log, channel, properties)

        



class QueueConsumer(object):
    """
    I consume things from a queue one at a time.
    """

    poll_interval = 1
    lc = None

    def __init__(self, channel, queue, consume):
        self.channel = channel
        self.queue = queue
        self.consume = consume


    def start(self):
        if self.lc:
            raise Exception("You can't start twice")
        self.lc = task.LoopingCall(self.tryForMessage)
        self.lc.start(self.poll_interval)


    def tryForMessage(self):
        message = self.channel.basic_get(self.queue, no_ack=False)
        if message[2]:
            self.lc.stop()
            self.lc = None
            d = defer.maybeDeferred(self.consume, self.channel, *message)
            d.addBoth(lambda _: self.start())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Connect an build a request')
    add_rabbit_host_arg(parser)
    parser.add_argument('--timeout', '-t', type=int, default=(20*60),
        help='Number of seconds processes are allowed to run')

    args = parser.parse_args()
    task.react(startBuilding, [args.rabbit_host, args.timeout])
