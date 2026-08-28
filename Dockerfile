FROM debian:bookworm-slim AS bgcode-builder
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates cmake g++ git make ninja-build python3 && rm -rf /var/lib/apt/lists/*
ARG LIBBGCODE_REF=main
RUN git clone --depth 1 --branch "${LIBBGCODE_REF}" https://github.com/prusa3d/libbgcode.git /src/libbgcode \
    && cd /src/libbgcode \
    && cmake --preset default -DLibBGCode_BUILD_DEPS=ON -DCMAKE_INSTALL_PREFIX=/opt/bgcode \
    && cmake --build --preset default --target install -j2

FROM node:22-bookworm-slim AS frontend-builder
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY app ./app
COPY components ./components
COPY hooks ./hooks
COPY lib ./lib
COPY public ./public
COPY .openai ./.openai
COPY components.json next.config.ts tsconfig.json vite.config.ts vite.spa.config.ts .oxfmtrc.json .oxlintrc.json ./
RUN npm run build:spa

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/bgcode/bin:${PATH}"
WORKDIR /app
RUN groupadd --gid 10001 filaflow && useradd --uid 10001 --gid filaflow --create-home filaflow
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=bgcode-builder /opt/bgcode /opt/bgcode
COPY backend ./backend
COPY --from=frontend-builder /src/dist/spa ./backend/web
RUN chmod +x /app/backend/entrypoint.sh && mkdir -p /config/uploads && chown -R filaflow:filaflow /app /config
USER filaflow
EXPOSE 9000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/api/health', timeout=3)"
ENTRYPOINT ["/app/backend/entrypoint.sh"]
