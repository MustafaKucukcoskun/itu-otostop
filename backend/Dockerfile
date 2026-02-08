FROM python:3.12-slim

WORKDIR /app

# ntplib için gerekli değil ama w32tm yerine chrony/ntpdate kullanılabilir
# Cloud Run'da NTP zaten çok hassas, ek paket gerekmez

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run $PORT env var verir, ona bind et
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --timeout-keep-alive 120"]
