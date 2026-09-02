FROM python:3.12-alpine AS deps
ENV PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.1.3 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN apk --no-cache upgrade
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app
COPY pyproject.toml poetry.lock /app/
RUN poetry install --only main


FROM deps AS dev
RUN poetry install --with dev
RUN apk add --no-cache git openssh-client-default curl aws-cli
CMD flask run --debug -h 0.0.0.0

# Release image without dev deps
FROM deps AS final
COPY . /app/
RUN addgroup -S kronic && adduser -S kronic -G kronic -u 3000
USER kronic
CMD gunicorn -w 4 -b 0.0.0.0 --access-logfile=- app:app
