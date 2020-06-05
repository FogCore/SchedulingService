#FROM python:3.7.7-slim-buster
FROM scheduling_service_base:latest

ADD . /SchedulingService
WORKDIR /SchedulingService

#RUN pip install --no-cache-dir --upgrade pip
#RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app.py"]
