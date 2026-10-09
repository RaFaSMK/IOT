FROM ollama/ollama:latest
RUN mkdir -p /models && chown -R 10001:10001 /models
ENV HOME=/tmp OLLAMA_MODELS=/models
USER 10001:10001
