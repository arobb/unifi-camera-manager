ARG BUILD_FROM
FROM ${BUILD_FROM}

WORKDIR /app

COPY app/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app/ .

CMD ["python3", "-u", "/app/main.py"]
