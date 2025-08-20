FROM python:3.11-slim
RUN pip install --no-cache-dir pyjwt==2.9.0 requests==2.32.3
WORKDIR /app
COPY init_secrets.py /app/init_secrets.py
CMD ["python", "/app/init_secrets.py"]