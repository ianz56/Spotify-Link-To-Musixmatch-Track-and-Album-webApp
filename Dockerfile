FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8556

ENTRYPOINT [ "hypercorn", "--bind", "0.0.0.0:8556" , "app:asgi_app" ]