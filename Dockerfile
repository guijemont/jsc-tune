FROM python:3.10-alpine as build

RUN apk update && apk add --no-cache dropbear-ssh \
	dropbear-scp \
	g++ \
	gfortran \
	musl-dev \
	pkgconf \
	openblas \
	openblas-dev \
	make


ENV PIP_ROOT_USER_ACTION=ignore

RUN pip install --no-cache-dir --no-warn-script-location --upgrade pip

RUN pip install --no-cache-dir --no-warn-script-location scikit-optimize==0.9.0

RUN pip install --no-cache-dir --no-warn-script-location matplotlib==3.5.3


### Runtime image

FROM python:3.10-alpine

RUN apk update && apk add --no-cache \
	dropbear-ssh \
	dropbear-scp \
	openblas \
	libstdc++ \
	libgomp

COPY --from=build /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# the following is to make matplotlib happy
RUN mkdir /matplotlib-tmp && chmod 777 /matplotlib-tmp
ENV MPLCONFIGDIR=/matplotlib-tmp

WORKDIR /work

ENTRYPOINT [ "python", "/jsc-tune/jsc-tune.py" ]
