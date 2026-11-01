FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m isa && chown -R isa /app
USER isa
EXPOSE 8501
# keys come from `docker run --env-file .env`, never baked into the image
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
