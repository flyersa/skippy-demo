FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
# web/ and assets/ are mounted at runtime (see docker-compose.yml) or COPYed in
# your own build. Defaults expect them at /app/web and /app/assets.
ENV DEMO_STATIC=/app/web DEMO_ASSETS=/app/assets PORT=8080
EXPOSE 8080
CMD ["python", "server.py"]
