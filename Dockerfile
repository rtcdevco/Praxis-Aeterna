FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ config/
COPY core/ core/
COPY face/ face/
COPY voice/ voice/
COPY vault_connector/ vault_connector/
COPY skills/ skills/
COPY vault/05-templates/ vault/05-templates/

# vault/ and skills/ are also mounted as volumes at run time (see README) so
# user notes and custom skills added after the image is built aren't lost —
# these COPY lines just seed a working default.
VOLUME ["/app/vault", "/app/skills"]

EXPOSE 8000

CMD ["uvicorn", "face.main:app", "--host", "0.0.0.0", "--port", "8000"]
