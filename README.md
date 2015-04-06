
This is a proof of concept (that might actually work pretty well) for a build system composed of easy-to-add docker-based builders.  Once the rabbit server is up, adding a build slave is a single docker command.

**Hey, this isn't secure!**  There's no authentication anywhere, and the builders will happily run any command you give them.


# Build cluster #

A build cluster consists of:

- 1 RabbitMQ server
- 1+ Build result noticer
- 1+ Builder


## Start RabbitMQ server ##

You only need 1 of these:

    docker run -p 5672:5672 -p 15672:15672 -e RABBITMQ_NODENAME=my-rabbit rabbitmq:management

XXX if you want the data to persist, you need to use volumes.

For the following steps, make sure you set RABBIT_HOST to where rabbit is available.
For instance:

    RABBIT_HOST=$DOCKER_HOST_IP


## Start a builder ##

**THIS IS PROBABLY NOT SAFE TO RUN ON A COMPUTER YOU CARE ABOUT**

Start as many of these as you want/need.  You will need to tell it where the rabbit host is:

    docker run --privileged -i -t -e RABBIT_HOST=$RABBIT_HOST dockerbuilder/builder

If you want to run it in the background:

    docker run --privileged -d -e RABBIT_HOST=$RABBIT_HOST dockerbuilder/builder


## Start a result logger ##

Either use this one (which is more colorful):

    docker run -i -t -e RABBIT_HOST=$RABBIT_HOST dockerbuilder/builddebug python process_watcher.py

Or use this one (which includes all data):

    docker run -i -t -e RABBIT_HOST=$RABBIT_HOST dockerbuilder/builddebug

Or both!


## Submit a build request ##

This will clone the dummy repo and list the files in it.

    docker run -e RABBIT_HOST=$RABBIT_HOST dockerbuilder/builddebug python submit_build_request.py --clone-url=https://github.com/iffy/dockerbuilder.git --name=john --revision=master --timeout=30 --step '{"args":["ls"], "env":{"FOO":"BAR"}}'



