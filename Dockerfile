FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
  git-core \
  && \
  rm -rf /var/lib/apt/lists/*

WORKDIR /src

ADD requirements_frozen.txt ./
RUN pip install -r ./requirements_frozen.txt

ADD version ./
ADD setup.py ./
ADD marge.app ./
ADD marge/ ./marge/
RUN python ./setup.py install

ENTRYPOINT ["marge.app"]
