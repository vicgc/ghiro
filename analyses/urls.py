# Ghiro - Copyright (C) 2013 Ghiro Developers.
# This file is part of Ghiro.
# See the file 'docs/LICENSE.txt' for license terms.

from django.conf.urls import patterns, url

urlpatterns = patterns("",
    url(r"^cases/$", "analyses.views.list_cases"),
    url(r"^cases/new/", "analyses.views.new_case"),
    url(r"^cases/edit/(?P<case_id>[\d]+)/", "analyses.views.edit_case"),
    url(r"^cases/close/(?P<case_id>[\d]+)/", "analyses.views.close_case"),
    url(r"^cases/delete/(?P<case_id>[\d]+)/", "analyses.views.delete_case"),
    url(r"^cases/show/(?P<case_id>[\d]+)/(?P<page_name>[\w]+)/", "analyses.views.show_case"),
    url(r"^cases/(?P<case_id>[\d]+)/images/new/$", "analyses.views.new_image"),
    url(r"^cases/(?P<case_id>[\d]+)/folder/new/$", "analyses.views.new_folder"),
    url(r"^cases/count_ajax/(?P<case_id>[\d]+)/(?P<analysis_id>[\d]+)/$", "analyses.views.count_new_analysis"),
    url(r"^show/(?P<analysis_id>[\d]+)/$", "analyses.views.show_analysis"),
    url(r"^images/(?P<page_name>[\w]+)/$", "analyses.views.list_images"),
    url(r"^images/file/(?P<id>[\d\w]+)/$", "analyses.views.image"),
    url(r"^images/favorite/(?P<id>[\d\w]+)/$", "analyses.views.favorite"),
    url(r"^search/(?P<page_name>[\w]+)/$", "analyses.views.search"),
)