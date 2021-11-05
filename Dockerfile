# FIXME: run as a user (and install pip packages as user)
# python 3.10 would be great, but can't build numpy with it
FROM python:3.9-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update  && apt-get upgrade -y && apt-get install -y \
	openssh-client \
	&& apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir scipy opentuner

RUN mkdir /work

WORKDIR /work

ENTRYPOINT [ "python", "./opentuner_js2.py" ]
