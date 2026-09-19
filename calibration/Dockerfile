FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir requests

COPY obs_clock_calibration.py obs_clock_probe.py ./

# Varsayılan: yeni hassas ölçüm aracı (eşzamanlı örnekleme).
# Eski araç da imajda duruyor; gerekirse komut değiştirilerek çalıştırılır.
CMD ["python", "-u", "obs_clock_probe.py"]
