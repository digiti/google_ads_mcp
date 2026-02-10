FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/digiti/google_ads_mcp"
LABEL org.opencontainers.image.description="Self-hosted Google Ads MCP Server with HTTP transport"
LABEL org.opencontainers.image.licenses="Apache-2.0"

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip && pip install uv

COPY pyproject.toml uv.lock ./
RUN uv pip install --system .

COPY . .
RUN uv pip install --system -e .

RUN useradd --create-home --shell /bin/bash mcpuser && \
    chown -R mcpuser:mcpuser /app
USER mcpuser

EXPOSE 8080

ENV GOOGLE_ADS_DEVELOPER_TOKEN=""
ENV GOOGLE_ADS_CLIENT_ID=""
ENV GOOGLE_ADS_CLIENT_SECRET=""
ENV GOOGLE_ADS_REFRESH_TOKEN=""
ENV GOOGLE_ADS_LOGIN_CUSTOMER_ID=""
ENV FASTMCP_PORT=8080
ENV FASTMCP_HOST=0.0.0.0
ENV LOG_LEVEL="INFO"

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('localhost', 8080)); s.close()"

CMD ["python", "-m", "ads_mcp.server"]
