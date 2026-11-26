FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Hugging Face Spaces runs containers as user 1000, so we do the same everywhere
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --user -r requirements.txt

COPY --chown=user . .

# Train inside the image so the saved model always matches the installed scikit-learn version
RUN python -m ml.train

ENV APP_ENV=production \
    DATABASE=/home/user/app/app.db \
    PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 60 wsgi:app"]