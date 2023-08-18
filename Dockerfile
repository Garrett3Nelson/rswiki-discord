ARG TOKEN
ARG DEBUG_GUILD
ARG USER_AGENT

FROM python:3.9-bookworm
ENV TOKEN $TOKEN
ENV DEBUG_GUILD $DEBUG_GUILD
ENV USER_AGENT $USER_AGENT
WORKDIR .
COPY requirements.txt wikibot.py ./
RUN pip install -r requirements.txt
CMD ["python", "wikibot.py"]