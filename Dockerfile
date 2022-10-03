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

FROM python:3.10-slim


RUN apt-get update  && apt-get upgrade -y && apt-get install -y \
	openssh-client \
	&& rm -rf /var/lib/apt/lists/*

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
