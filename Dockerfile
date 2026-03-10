FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use -u for unbuffered logging
CMD ["python", "-u", "main.py"]
