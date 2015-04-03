import pika
import argparse
import json

from simplebuilder.common import makeBuildRequest, declareThings
from simplebuilder.common import add_rabbit_host_arg



def submitBuildRequest(rabbit_host, name, clone_url, revision, steps, timeout):
    conn = pika.BlockingConnection(pika.ConnectionParameters(rabbit_host))
    channel = conn.channel()
    declareThings(channel)
    makeBuildRequest(channel, name, clone_url, revision, steps, timeout)
    conn.close()


def json_step(x):
    d = json.loads(x)
    assert isinstance(d, dict)
    return d


def env_dict(x):
    key, value = x.split('=', 1)
    d = {}
    d[key] = value
    return d


def prepSteps(args):
    steps = list(args.step)
    if not args.no_clone_step:
        # http://stackoverflow.com/questions/3489173/how-to-clone-git-repository-with-specific-revision-changeset
        steps = [
        {
            'args': ['git', 'init', '.'],
        },
        {
            'args': ['git', 'remote', 'add', 'origin', args.clone_url],
        },
        {
            'args': ['git', 'fetch', 'origin', '--depth', '1', args.revision],
        },
        {
            'args': ['git', 'reset', '--hard', 'FETCH_HEAD'],
        },
        ] + steps
    return steps

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Submit a build request')
    add_rabbit_host_arg(parser)
    parser.add_argument('--name', '-n',
        required=True,
        help='Name of build type (for instance "pyflakes" or "trial")')
    parser.add_argument('--clone-url', '-u',
        required=True,
        help='Clone URL')
    parser.add_argument('--revision', '-r',
        default='master',
        help='Revision/branch/SHA')
    parser.add_argument('--no-clone-step', '-C',
        action='store_true',
        default=False,
        help="Use this if you don't want a clone step to be automatically done first")
    parser.add_argument('--step', '-s',
        action='append',
        type=json_step,
        help='JSON-encoded dictionary of a step to run.  May be specified multiple'
             ' times')
    parser.add_argument('--timeout', '-t',
        type=int,
        default=(30*60),
        help='Timeout for each build step (i.e. commands will be killed '
            'if they takes longer than this number of seconds)')

    args = parser.parse_args()
    # I'm sure argparse has a built-in way of doing this, but I'm just doing a prototype
    steps = prepSteps(args)
    submitBuildRequest(args.rabbit_host, args.name, args.clone_url, args.revision, steps, args.timeout)
