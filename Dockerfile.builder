FROM iffy/dind
MAINTAINER matt

RUN apt-get update
RUN apt-get install -y python-dev
RUN apt-get install -y python-pip

COPY requirements.txt /work/requirements.txt
RUN pip install -U -r /work/requirements.txt

ADD . /work/

WORKDIR /work

ENV LOG="file"
CMD ["wrapdocker", "python", "trusting_builder.py"]