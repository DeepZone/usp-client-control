FROM python:3.13-slim AS proto
RUN pip install --no-cache-dir grpcio-tools==1.74.0
WORKDIR /build
COPY proto/ .
RUN mkdir -p /generated && python -m grpc_tools.protoc -I. --python_out=/generated usp-msg.proto usp-record.proto

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --system --uid 10001 --home /app usp
COPY --from=proto /generated/usp_msg_pb2.py /generated/usp_record_pb2.py /app/
COPY app.py .
COPY VERSION .
COPY static static
RUN mkdir /data && chown usp:usp /data
USER usp
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--ws", "wsproto"]
