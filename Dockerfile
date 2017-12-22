FROM ubuntu:trusty

MAINTAINER Reinout van Rees <reinout.vanrees@nelen-schuurmans.nl>

# Change the date to force rebuilding the whole image
ENV REFRESHED_AT 1972-12-25

# system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    python-software-properties \
    software-properties-common \
    apt-transport-https \
    wget \
&& apt-get clean -y

RUN add-apt-repository 'deb http://ppa.launchpad.net/ubuntugis/ppa/ubuntu precise main'

RUN apt-get update && apt-get install -y \
    python-dev \
    python-pip \
    python-psycopg2 \
    python-matplotlib \
    python-gdal \
    gdal-bin \
    gettext \
    postgresql-client \
&& apt-get clean -y
RUN pip install --upgrade setuptools zc.buildout

RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

WORKDIR /code
