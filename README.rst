.. image:: https://travis-ci.org/openprocurement/openregistry.api.svg?branch=master
    :target: https://travis-ci.org/openprocurement/openregistry.api


.. image:: https://coveralls.io/repos/openprocurement/openregistry.api/badge.svg
  :target: https://coveralls.io/r/openprocurement/openregistry.api

.. image:: https://img.shields.io/hexpm/l/plug.svg
    :target: https://github.com/openprocurement/openregistry.api/blob/master/LICENSE.txt


Documentation
=============

Swagger docs
------------
To get swagger docs, you may just make `GET` request on::

    /api/<version>/swagger

You also must check if the plugins connected directly, i.e you must check if any
views use the same URL and disable conflicting ones.

