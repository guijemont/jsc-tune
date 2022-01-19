# FIXME: run as a user (and install pip packages as user)
# python 3.10 would be great, but can't build numpy with it
FROM python:3.9-slim

ARG user=optimizer
ARG uid=1001
ARG group=optimizer
ARG gid=1001

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update  && apt-get upgrade -y && apt-get install -y \
	openssh-client \
	&& apt-get clean && rm -rf /var/lib/apt/lists/*


RUN echo $gid:$group && groupadd -g "$gid" "$group"

RUN useradd -m -u "$uid" -g "$gid" "$user"


RUN mkdir /work && chown $uid:$gid /work

WORKDIR /work

USER $user

RUN pip install --no-cache-dir --no-warn-script-location --upgrade pip && pip install --no-cache-dir --no-warn-script-location scipy scikit-optimize matplotlib

ENTRYPOINT [ "python", "./scikit-optimize-js2.py" ]
