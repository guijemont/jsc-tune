# Copyright (C) 2022 Igalia S.L.
#
# This file is part of jsc-tune.
#
# Jsc-tune is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# Jsc-tune is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# jsc-tune. If not, see <https://www.gnu.org/licenses/>.

FROM python:3.10-slim as build

ENV DROPBEAR_VERSION=2022.82

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update  && apt-get upgrade -y && apt-get install -y \
	build-essential \
	zlib1g-dev \
	&& rm -rf /var/lib/apt/lists/*

RUN mkdir /work

WORKDIR /work

# openssh doesn't want to run when running it under `docker run --user <user>`,
# so we need to use dropbear. Unfortunately, debian does not provide scp with
# dropbear, so we have to build our own, hence the multi-stage build.
# See https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=495795
ADD https://matt.ucc.asn.au/dropbear/releases/dropbear-${DROPBEAR_VERSION}.tar.bz2 /work

RUN tar xf dropbear-${DROPBEAR_VERSION}.tar.bz2 \
	&& cd dropbear-${DROPBEAR_VERSION} \
	&& ./configure --prefix=/usr \
            --sysconfdir=/etc \
            --mandir=/usr/share/man \
            --infodir=/usr/share/info \
            --localstatedir=/var \
            --disable-wtmp \
            --disable-lastlog \
            --disable-shadow \
	&& make dbclient scp dropbearconvert \
	&& mv dbclient scp dropbearconvert ../

### Runtime image

FROM python:3.10-slim

COPY --from=build /work/dbclient /work/scp /work/dropbearconvert /usr/bin/
RUN ln -s /usr/bin/dbclient /usr/bin/ssh

ENV PIP_ROOT_USER_ACTION=ignore

RUN pip install --no-cache-dir --no-warn-script-location --upgrade pip

RUN pip install --no-cache-dir --no-warn-script-location \
	scikit-optimize==0.9.0 \
	matplotlib==3.5.3

# the following is to make matplotlib happy
RUN mkdir /matplotlib-tmp && chmod 777 /matplotlib-tmp
ENV MPLCONFIGDIR=/matplotlib-tmp

RUN mkdir -p /jsc-tune-data/ssh && chmod 777 /jsc-tune-data/ssh

RUN mkdir -p /work && chmod 777 /work

ENV HOME=/work

WORKDIR /jsc-tune

ENTRYPOINT [ "python", "-u", "jsc-tune.py" ]
