#docker build -t flight-svc1 .

FROM ubuntu:22.04 AS base

ENV TZ=Europe/London
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_CONFIG_FILE=pip.conf



# Install dependencies needed for building Python and other packages
RUN apt-get update  \
    && apt-get install -y --no-install-recommends \
    build-essential zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev wget curl llvm \
    libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev \
    && apt-get install -y apt-transport-https

# Download and install Python 3.9
RUN apt-get update  \
    && apt-get install -y --allow-downgrades python3-venv python3 python3-pip python3-dev python3-setuptools python3-wheel python3-apt



#RUN apt-get install -y python3.9.13 \
#    && ln -s /usr/bin/python3.9.13 /usr/bin/python3



# Create a virtual environment (recommended)
RUN python3 -m venv /venv

# Activate the virtual environment
ENV VIRTUAL_ENV="/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

USER root

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/
WORKDIR /app/

RUN useradd -ms /bin/bash my_user  # Create the user 'my_user'
RUN chown -R my_user /app/


#RUN rm -R /certs
RUN chown -R my_user /app/
RUN chmod 755 /app/

#RUN mkdir -p ./zk1/data ./zk1/datalog ./zk1/conf
#RUN chmod -R 755 ./zk1/data ./zk1/datalog ./zk1/conf


EXPOSE 8080

USER my_user
CMD ["python", "wsgi.py"]
#CMD ["gunicorn", "--bind 0.0.0.0.:8080", "--log-level=debug", "wsgi:simpleapi"]