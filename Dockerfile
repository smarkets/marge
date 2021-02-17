FROM ubuntu:18.04
RUN apt-get update && apt-get install \
    -y build-essential git python3-dev python3-virtualenv

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m virtualenv --python=/usr/bin/python3 $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install dependencies:
COPY setup.py marge-bot/setup.py
COPY requirements.txt marge-bot/requirements.txt
COPY requirements_frozen.txt marge-bot/requirements_frozen.txt
COPY version marge-bot/version
COPY marge marge-bot/marge
COPY marge.app marge-bot/marge.app

WORKDIR /marge-bot

RUN python3 setup.py install
RUN pip3 install -r requirements.txt

ENTRYPOINT ["./marge.app"]
