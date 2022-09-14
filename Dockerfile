# FIXME: run as a user (and install pip packages as user)
# python 3.10 would be great, but can't build numpy with it
#FROM python:3.9-slim
FROM python:3.9-alpine

ARG user=optimizer
ARG uid=1001
ARG group=optimizer
ARG gid=1001

#ENV DEBIAN_FRONTEND=noninteractive

# RUN apt-get update  && apt-get upgrade -y && apt-get install -y \
# 	openssh-client \
# 	&& apt-get clean && rm -rf /var/lib/apt/lists/*

RUN apk update && apk add --no-cache dropbear-ssh dropbear-scp gfortran

# RUN echo $gid:$group && groupadd -g "$gid" "$group"

RUN addgroup -g "$gid" "$group"

# RUN useradd -m -u "$uid" -g "$gid" "$user"

RUN adduser -G "$group" -u "$uid" -D "$user"


RUN mkdir /work && chown $uid:$gid /work

RUN mkdir /jsc-tune && chown $uid:$gid /jsc-tune

RUN mkdir -p /jsc-tune-data/ssh /jsc-tune-data/benchmark && chown -R $uid:$gid /jsc-tune-data

WORKDIR /work

USER $user

RUN pip install --no-cache-dir --no-warn-script-location --upgrade pip

# RUN pip install --no-cache-dir --no-warn-script-location scipy==1.9.1

RUN pip install --no-cache-dir --no-warn-script-location --user scikit-optimize==0.9.0

RUN pip install --no-cache-dir --no-warn-script-location --user matplotlib==3.5.3


ENTRYPOINT [ "python", "/jsc-tune/jsc-tune.py" ]
