# Мини-апп собирается здесь же и кладётся внутрь пакета backend: отдельного
# контейнера со статикой нет, её отдаёт то же приложение, что и API.
FROM node:24-alpine AS miniapp
WORKDIR /build/miniapp
COPY miniapp/package.json miniapp/package-lock.json ./
RUN npm ci
COPY miniapp/ ./
# vite пишет в ../backend/src/vocab/api/static — каталог должен существовать.
RUN mkdir -p /build/backend/src/vocab/api && npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY backend/ ./
COPY --from=miniapp /build/backend/src/vocab/api/static ./src/vocab/api/static
RUN pip install --no-cache-dir .

# Приложение не должно иметь права переписать собственный код.
RUN useradd --create-home --uid 10001 vocab && chown -R root:root /app
USER vocab

EXPOSE 8000
CMD ["uvicorn", "vocab.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
