FROM python:3.12-slim
WORKDIR /app
COPY bonprinter.py index.html ./
EXPOSE 8765
CMD ["python", "bonprinter.py"]
