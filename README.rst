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
There is `fork <https://github.com/bdmbdsm/cornice.ext.swagger>`_ of `cornice_swagger`,
adapted to work with **OpenProcurement** and **OpenRegistry**.
If you'll install it, docstrings of views will be included into swagger-docs on
output.

Example of fork's installation into buildout of `OpenProcurement <https://github.com/openprocurement/openprocurement.buildout/tree/production>`_

`installation commit <https://github.com/bdmbdsm/openprocurement.buildout/commit/6dd5d4049b55728c33b3023a7d70cf7e547dff85>`_

To get swagger docs, you may just make `GET` request on::

    /api/<version>/swagger

You also must check if the plugins connected directly, i.e you must check if any
views use the same URL and disable conflicting ones.

