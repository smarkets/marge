FROM python:3.9-slim AS builder

ARG POETRY_VERSION=1.1.4
RUN pip install poetry==$POETRY_VERSION

WORKDIR /src

COPY pyproject.toml poetry.lock README.md pylintrc ./
COPY marge/ ./marge/
RUN poetry export -o requirements.txt && \
  poetry build


FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
  git-core \
  && \
  rm -rf /var/lib/apt/lists/*

COPY --from=builder /src/requirements.txt /src/dist/marge-*.tar.gz /tmp/

RUN pip install -r /tmp/requirements.txt && \
  pip install /tmp/marge-*.tar.gz

ENTRYPOINT ["marge"]
