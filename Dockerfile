ARG TOKEN
ARG DEBUG_GUILD
ARG USER_AGENT

FROM python:3.9-bookworm
ENV TOKEN $TOKEN
ENV DEBUG_GUILD $DEBUG_GUILD
ENV USER_AGENT $USER_AGENT
COPY requirements.txt wikibot.py ./
COPY stack.env ./.env
RUN pip install -r requirements.txt
CMD ["python", "wikibot.py"]