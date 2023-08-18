FROM python:3.9-bookworm
WORKDIR .
RUN pip install -r requirements.txt
CMD ["python", "wikipot.py"]
