# syntax=docker/dockerfile:1
# NOTE: base images are tag@digest on purpose (Sonar docker:S8431 accepted). The digest
# pins the build; the tag is what Dependabot follows to propose a new digest (it doesn't
# read comments here, and digest-only would follow `latest`). Docker ignores the
# tag when a digest is given. Tags without an Alpine version: those stop getting builds
# when Alpine moves on, and Dependabot keeps the old suffix.

# The page's script and styles (esbuild), Floating UI and the fonts; only these files
# reach the final image, not Node
FROM --platform=$BUILDPLATFORM node:26-alpine@sha256:0b36e8c136b94cd4fcf02188228e76c31ad5872eef3fec8cbd2eee500cfd9e80 AS page
WORKDIR /page
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund
COPY src/js/ ./src/js/
COPY src/css/ ./src/css/
RUN node --run build

FROM python:3.13-alpine@sha256:2dd78ad5cf13a0b68f5134dc49aa9950203a8cf4b7463431b9f3b398287c5059

# pip goes: nothing is installed at runtime, and its vendored libraries only add CVEs
RUN apk upgrade --no-cache \
    && apk add --no-cache tini openssh-client supercronic tzdata \
    && python -m pip uninstall --yes --quiet pip \
    && rm -rf "$(python -c 'import ensurepip, os; print(os.path.dirname(ensurepip.__file__))')/_bundled" \
    && adduser -D -u 10001 marqueefin \
    && install -d -o marqueefin -g marqueefin /data

# The release workflow adds version, revision and source
LABEL org.opencontainers.image.title="Marqueefin" \
      org.opencontainers.image.description="Your Jellyfin library as one shareable page, built on a schedule and uploaded over SFTP" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app
COPY export.py ./
COPY marqueefin/ ./marqueefin/
COPY src/template.html src/favicon.svg ./src/
COPY src/i18n/ ./src/i18n/
COPY --from=page /page/build/ ./build/
COPY --from=page /page/node_modules/@floating-ui/ ./node_modules/@floating-ui/
COPY --from=page /page/node_modules/@fontsource-variable/ ./node_modules/@fontsource-variable/
COPY --chmod=0755 docker/*.sh ./docker/
COPY docker/notify.py ./docker/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC \
    EXPORT_OUTPUT=/data/collection.html \
    EXPORT_CACHE_DIR=/data/cache

VOLUME /data
# Numeric, so runAsNonRoot checks work without /etc/passwd
USER 10001

# Scheduled mode only. The first check waits for the first run (hence the timeout),
# so `docker compose up --wait` returns when it's done; one failed run is unhealthy.
HEALTHCHECK --interval=1m --timeout=30m --start-period=1s --start-interval=1s --retries=1 \
    CMD ["/app/docker/healthcheck.sh"]

ENTRYPOINT ["/sbin/tini", "--", "/app/docker/entrypoint.sh"]
