import pika
import argparse
import json

from simplebuilder.common import makeTemporaryStatusQueue
from simplebuilder.common import declareThings, add_rabbit_host_arg

BOLD = '\033[1m'
ENDC = '\033[0m'
BLUE = '\033[94m'
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'


class Printer(object):

    last_prefix = None

    def callback(self, ch, method, properties, body):
        try:
            key = method.routing_key
            m = getattr(self, 'handle_'+key.replace('.','_'), None)
            req_id = properties.correlation_id
            prefix = req_id
            if m:
                m(prefix, body)
        except Exception as e:
            print 'ERROR: %r' % (e,)
            raise


    def pp(self, prefix, message):
        if prefix != self.last_prefix:
            self.last_prefix = prefix
            print '\n' + BOLD + '---' + prefix + '---' + ENDC
        print message


    def handle_build_request(self, prefix, body):
        self.pp(prefix, BLUE + 'BUILD REQUESTED' + ENDC)
        data = json.loads(body)
        self.pp(prefix, (
            '  clone_url: %(clone_url)s\n'
            '  revision:  %(revision)s\n'
            '  name:      %(name)s\n'
            '  steps:' % data
        ))
        for step in data['steps']:
            self.pp(prefix,
                '    %r' % (step['args'],))
            if 'env' in step:
                self.pp(prefix,
                    '    %r' % (step['env'],))



    def handle_build_finish(self, prefix, body):
        data = json.loads(body)
        color = FAIL
        if data['success']:
            color = OKGREEN
        self.pp(prefix,
            (color + 'BUILD FINISHED -- success? %(success)r' + ENDC) % data)

    def handle_build_status(self, prefix, body):
        data = json.loads(body)
        m = getattr(self, 'handleevent_'+data['event'], None)
        if m:
            m(prefix, data)
        else:
            self.pp(prefix, '(' + data['event'] + ')')

    def handleevent_process_started(self, prefix, data):
        self.pp(prefix, BOLD + '> ' + data['pname'] + ENDC)


    def handleevent_process_ended(self, prefix, data):
        self.pp(prefix,
            BOLD + '[' + str(data['rc']) + '] %ss' % (data['runtime'],) + ENDC)


    def handleevent_stdout(self, prefix, data):
        self.pp(prefix, data['data'])
    handleevent_stderr = handleevent_stdout




def startPrinting(rabbit_host):
    parameters = pika.ConnectionParameters(rabbit_host)
    conn = pika.BlockingConnection(parameters)
    channel = conn.channel()
    declareThings(channel)
    queue = makeTemporaryStatusQueue(channel)

    printer = Printer()

    channel.basic_consume(printer.callback,
        queue=queue,
        no_ack=True)
    channel.start_consuming()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Connect an build a request')
    add_rabbit_host_arg(parser)
    
    args = parser.parse_args()
    startPrinting(args.rabbit_host)
