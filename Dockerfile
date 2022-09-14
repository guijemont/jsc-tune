# FIXME python 3.10 would be great; can it work?
FROM python:3.9-alpine as build

ARG user=optimizer
ARG uid=1001
ARG group=optimizer
ARG gid=1001

RUN apk update && apk add --no-cache dropbear-ssh \
	dropbear-scp \
	g++ \
	gfortran \
	musl-dev \
	pkgconf \
	openblas \
	openblas-dev \
	make


RUN addgroup -g "$gid" "$group"

RUN adduser -G "$group" -u "$uid" -D "$user"

USER $user

RUN pip install --no-cache-dir --no-warn-script-location --upgrade pip

RUN pip install --no-cache-dir --no-warn-script-location --user scikit-optimize==0.9.0

RUN pip install --no-cache-dir --no-warn-script-location --user matplotlib==3.5.3


### Runtime image

FROM python:3.9-alpine

ARG user=optimizer
ARG uid=1001
ARG group=optimizer
ARG gid=1001

RUN addgroup -g "$gid" "$group" && adduser -G "$group" -u "$uid" -D "$user"

RUN apk update && apk add --no-cache \
	dropbear-ssh \
	dropbear-scp \
	openblas \
	libstdc++ \
	libgomp

RUN mkdir /work && chown $uid:$gid /work \
	&& mkdir /jsc-tune && chown $uid:$gid /jsc-tune \
	&& mkdir -p /jsc-tune-data/ssh /jsc-tune-data/benchmark && chown -R $uid:$gid /jsc-tune-data

WORKDIR /work

COPY --from=build /home/$user/.local /home/$user/.local

USER $user

ENTRYPOINT [ "python", "/jsc-tune/jsc-tune.py" ]
