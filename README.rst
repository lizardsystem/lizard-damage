lizard-damage
==========================================

Lizard-damage is the functionality of the "Waterschadeschatter" site,
in a Django app. It's also a Lizard app, but besides using the Lizard
base template, hardly any of its functionality is used.


Local development with docker
-----------------------------

Prerequisite: recent docker install (including docker-compose).

One-time setup::

    $ docker-compose build
    $ docker-compose web run python bootstrap.py
    $ docker-compose web run bin/buildout
    $ docker-compose web run bin/django syncdb
    $ docker-compose web run bin/django migrate

Regular commands::

    $ docker-compose web run bin/test
    $ docker-compose up

Alternatively to the last one::

    $ docker-compose run --service-ports web bin/django runserver 0.0.0.0:5000
