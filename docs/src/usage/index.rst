Usage
=====

Ghiro's web application is composed by several parts to organize information and analysis data.

Dashboard
---------

This is the summary of all Ghiro activities, here you can figure what is going on, which are the last
cases and analysis, and take a look to analysis trend.

Cases
-----

Image analysis are grouped in cases. Different users and permissions can be assigned to each case.
You can upload images via an upload form ("Add image" function) or you can get the images from a
path on the Ghiro's server ("Add folder" function).
Here you can see all analysis related to images grouped by case.

Images
------

Here you can see all image analysis in the system (all images you have permission to see).

Search
------

You can search for several image properties or for image location.

Hashes
------

You can load hash lists to detect if an image met an hash.

Administration
--------------

Ghiro user administration: you can administer all Ghiro's users.

Administration
==============

Some hints about Ghiro administration.

Run processor in debug mode
---------------------------

If you need to run the image processor deamon in debug mode to debug tracebacks
run the following command (inside Ghiro's root)::

    python manage.py process --traceback

Create a new superuser
----------------------

If you need to create a new superuser from the command lince, for example
because you closed you out from the web interface, run the following command
(inside Ghiro's root)::

    python manage.py createsuperuser

Upload images via command line utility
--------------------------------------

If you need to load tons of images you can do it from command line.
For example if you want to add all images in folder /target/images to case with id
2 and owner user name "foobar" run the following command (inside Ghiro's root)::

    python manage.py submit -u foobar -c 2 -t /target/images

And all images will be loaded in a batch.