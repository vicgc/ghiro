# Ghiro - Copyright (C) 2013 Ghiro Developers.
# This file is part of Ghiro.
# See the file 'docs/LICENSE.txt' for license terms.

import gridfs
import os
import re
import magic
from bson.son import SON
from bson.objectid import ObjectId, InvalidId
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_safe
from django.shortcuts import render_to_response, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.utils.timezone import now
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count

import analyses.forms as forms
from analyses.models import Case, Analysis
from users.models import Profile
from analyzer.db import save_file, get_file
from analyzer.utils import create_thumb
from ghiro.common import log_activity, mongo_connect

# Mongo connection.
db = mongo_connect()
fs = gridfs.GridFS(db)

@login_required
def new_case(request):
    """Creates a new case."""
    if request.method == "POST":
        form = forms.CaseForm(request.POST)
        if form.is_valid():
            case = form.save(commit=False)
            case.owner = request.user
            case.save()
            form.save_m2m()
            # Always add owner.
            case.users.add(request.user)
            # Auditing.
            log_activity("C",
                         "Created new case {0}".format(case.name),
                         request)
            return HttpResponseRedirect(reverse("analyses.views.show_case", args=(case.id, "list")))
    else:
        form = forms.CaseForm()

    return render_to_response("analyses/cases/new.html",
                              {"form": form},
                              context_instance=RequestContext(request))

@login_required
def edit_case(request, case_id):
    """Edit a case."""
    case = get_object_or_404(Case, pk=case_id)

    # Security check.
    if request.user != case.owner and not request.user.is_superuser:
        return render_to_response("error.html",
                                  {"error": "You are not authorized to edit this."},
                                  context_instance=RequestContext(request))

    if case.state == "C":
        return render_to_response("error.html",
                                  {"error": "You cannot edit a closed case."},
                                  context_instance=RequestContext(request))

    if request.method == "POST":
        form = forms.CaseForm(request.POST, instance=case)
        if form.is_valid():
            case = form.save(commit=False)
            case.owner = request.user
            case.updated_at = now()
            case.save()
            form.save_m2m()
            # Always add owner.
            case.users.add(request.user)
            # Auditing.
            log_activity("C",
                         "Edited case {0}".format(case.name),
                         request)
            return HttpResponseRedirect(reverse("analyses.views.show_case", args=(case.id, "list")))
    else:
        form = forms.CaseForm(instance=case)

    # Redirects to case index if requested.
    if request.GET.get("page", None):
        return HttpResponseRedirect(reverse("analyses.views.list_cases"))
    else:
        return render_to_response("analyses/cases/edit.html",
                                  {"form": form, "case": case},
                                  context_instance=RequestContext(request))

@login_required
def close_case(request, case_id):
    """Close a case."""
    case = get_object_or_404(Case, pk=case_id)

    # Security check.
    if request.user != case.owner and not request.user.is_superuser:
        return render_to_response("error.html",
                                  {"error": "You are not authorized to close this."},
                                  context_instance=RequestContext(request))

    if case.state == "C":
        return render_to_response("error.html",
                                  {"error": "You cannot edit an already closed case."},
                                  context_instance=RequestContext(request))

    case.state = "C"
    case.updated_at = now()
    case.save()
    # Auditing.
    log_activity("C",
                 "Closed case {0}".format(case.name),
                 request)
    return HttpResponseRedirect(reverse("analyses.views.list_cases"))

@require_safe
@login_required
def delete_case(request, case_id):
    """Delete a case."""
    case = get_object_or_404(Case, pk=case_id)

    # Security check.
    if request.user != case.owner and not request.user.is_superuser:
        return render_to_response("error.html",
                                  {"error": "You are not authorized to delete this."},
                                  context_instance=RequestContext(request))

    Case.objects.get(pk=case_id).delete()

    # Auditing.
    log_activity("C",
                 "Case {0} deleted".format(case.name),
                 request)
    return HttpResponseRedirect(reverse("analyses.views.list_cases"))

@require_safe
@login_required
def show_case(request, case_id, page_name):
    """Details about a case."""
    case = get_object_or_404(Case, pk=case_id)

    # Security check.
    if not request.user in case.users.all() and not request.user.is_superuser:
        return render_to_response("error.html",
            {"error": "You are not authorized to view this."},
            context_instance=RequestContext(request))

    tasks = Analysis.objects.filter(case=case)

    # Get last image.
    if tasks.filter(state="C").order_by("completed_at").exists():
        last_image = tasks.filter(state="C").order_by("-id")[0].id
    else:
        last_image = 0

    page = request.GET.get("page")
    if page_name == "list" or page_name == "thumb":
        tasks = _paginate(tasks, page, 20)
    elif page_name == "owned":
        tasks = tasks.filter(owner=request.user)
        tasks = _paginate(tasks, page, 20)
    elif page_name == "others":
        tasks = tasks.exclude(owner=request.user)
        tasks = _paginate(tasks, page, 20)
    elif page_name == "map":
        # Return all data, lookup on mongo to be faster.
        mongo_results = db.analyses.find({"metadata.gps.pos": {"$exists": True}})
        # Get results (run a bunch of queries to avoid too long sql queries).
        tasks = []
        for result in mongo_results:
            try:
                analyses = Analysis.objects.filter(case=case)
                if not request.user.is_superuser:
                    analyses = analyses.filter(Q(case__owner=request.user) | Q(case__users=request.user))
                tasks.append(analyses.get(analysis_id=result["_id"]))
            except ObjectDoesNotExist:
                continue
    else:
        raise Exception

    return render_to_response("analyses/cases/show.html",
                              {"case": case, "tasks": tasks, "last_image": last_image, "pagename": page_name},
                              context_instance=RequestContext(request))

@require_safe
@login_required
def count_new_analysis(request, case_id, analysis_id):
    """Count new analysis."""
    case = get_object_or_404(Case, pk=case_id)
    new_analysis_count = Analysis.objects.filter(case=case).filter(state="C").filter(pk__gt=analysis_id).count()
    return HttpResponse(new_analysis_count)

@require_safe
@login_required
def list_cases(request):
    """Cases index."""
    last = Case.objects.all()
    my = Case.objects.filter(owner=request.user)
    others = Case.objects.exclude(owner=request.user)

    # Only superuser can see all.
    if not request.user.is_superuser:
        last = last.filter(Q(owner=request.user) | Q(users=request.user))

    # Set sidebar active tab.
    request.session["sidebar_active"] = "side-cases"

    return render_to_response("analyses/cases/index.html",
                              {"my_cases": my, "last_cases": last, "others_cases": others},
                              context_instance=RequestContext(request))

@login_required
def new_image(request, case_id):
    """Upload a new image."""
    case = get_object_or_404(Case, pk=case_id)

    # Security check.
    if not request.user.is_superuser and not request.user in case.users.all():
        return render_to_response("error.html",
                                  {"error": "You are not authorized to add image to this."},
                                  context_instance=RequestContext(request))

    if case.state == "C":
        return render_to_response("error.html",
                                  {"error": "You cannot add an image to a closed case."},
                                  context_instance=RequestContext(request))

    if request.method == "POST":
        form = forms.UploadImageForm(request.POST, request.FILES)
        if form.is_valid():
            task = form.save(commit=False)
            task.owner = request.user
            task.case = case
            task.file_name = request.FILES["image"].name
            task.image_id = save_file(file_path=request.FILES["image"].temporary_file_path(),
                                      content_type=request.FILES["image"].content_type)
            task.thumb_id = create_thumb(request.FILES["image"].temporary_file_path())
            task.save()
            # Auditing.
            log_activity("I",
                         "Created new analysis {0}".format(task.file_name),
                         request)
            return HttpResponseRedirect(reverse("analyses.views.show_case", args=(case.id, "list")))
    else:
        form = forms.UploadImageForm()

    return render_to_response("analyses/images/new_image.html",
                              {"form": form, "case": case},
                              context_instance=RequestContext(request))

@login_required
def new_folder(request, case_id):
    """Load files from a local directory."""
    case = get_object_or_404(Case, pk=case_id)

    # Security check.
    if not(request.user.is_superuser or request.user in case.users.all()):
        return render_to_response("error.html",
                                  {"error": "You are not authorized to add image to this."},
                                  context_instance=RequestContext(request))

    if case.state == "C":
        return render_to_response("error.html",
                                  {"error": "You cannot add an image to a closed case."},
                                  context_instance=RequestContext(request))

    if request.method == "POST":
        form = forms.ImageFolderForm(request.POST)
        if form.is_valid():
            # Check.
            if not os.path.exists(request.POST.get("path")):
                return render_to_response("error.html",
                    {"error": "Folder does not exist."},
                    context_instance=RequestContext(request))
            elif not os.path.isdir(request.POST.get("path")):
                return render_to_response("error.html",
                    {"error": "Folder is not a directory."},
                    context_instance=RequestContext(request))
            # Add all files in directory.
            for file in os.listdir(request.POST.get("path")):
                task = Analysis()
                task.owner = request.user
                task.case = case
                task.file_name = file
                mime = magic.Magic(mime=True)
                task.image_id = save_file(file_path=os.path.join(request.POST.get("path"), file),
                                          content_type=mime.from_file(os.path.join(request.POST.get("path"), file)))
                task.thumb_id = create_thumb(os.path.join(request.POST.get("path"), file))
                task.save()
                # Auditing.
                log_activity("I",
                             "Created new analysis {0}".format(task.file_name),
                             request)
            return HttpResponseRedirect(reverse("analyses.views.show_case", args=(case.id, "list")))
    else:
        form = forms.ImageFolderForm()

    return render_to_response("analyses/images/new_folder.html",
                              {"form": form, "case": case},
                              context_instance=RequestContext(request))
@require_safe
@login_required
def show_analysis(request, analysis_id):
    """Shows report."""
    analysis = get_object_or_404(Analysis, pk=analysis_id)

    # Security check.
    if not(request.user.is_superuser or request.user in analysis.case.users.all()):
        return render_to_response("error.html",
                                  {"error": "You are not authorized to view this."},
                                  context_instance=RequestContext(request))

    if analysis.state == "C":
        try:
            anal = db.analyses.find_one(ObjectId(analysis.analysis_id))

            if anal:
                return render_to_response("analyses/report/show.html",
                                          {"anal": anal, "analysis": analysis},
                                          context_instance=RequestContext(request))
            else:
                return render_to_response("error.html",
                                          {"error": "Analysis not present in mongo database"},
                                          context_instance=RequestContext(request))
        except InvalidId:
            return render_to_response("error.html",
                                      {"error": "Analysis not found"},
                                      context_instance=RequestContext(request))
    elif analysis.state == "W":
        return render_to_response("analyses/images/waiting.html",
                                  {"analysis": analysis},
                                  context_instance=RequestContext(request))
    elif analysis.state == "E":
        return render_to_response("error.html",
                                  {"error": "Analysis ended with error."},
                                  context_instance=RequestContext(request))
    else:
        return render_to_response("error.html",
                                  {"error": "Analysis not found"},
                                  context_instance=RequestContext(request))

@require_safe
@login_required
def image(request, id):
    try:
       file = get_file(id)
    except (InvalidId, TypeError):
        return render_to_response("error.html",
                                  {"error": "Unable to load image."},
                                  context_instance=RequestContext(request))

    data = file.read()
    response = HttpResponse(data, content_type=file.content_type)
    response["Content-Disposition"] = "attachment; filename=%s" % id
    response["Content-Length"] = len(data)
    return response

def _paginate(data, page, num):
    """Paginates data.
    @param data: data to be paginated
    @param page: current page
    @param num: how many entries per page
    """
    # Show num entries per page.
    paginator = Paginator(data, num)
    try:
        data = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        data = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        data = paginator.page(paginator.num_pages)
    return data

@require_safe
@login_required
def list_images(request, page_name):
    last = Analysis.objects.filter(state="C")
    # Superuser can see all.
    if not request.user.is_superuser:
        last = last.filter(Q(owner=request.user) | Q(case__users=request.user))

    if page_name == "list" or page_name == "thumb":
        page = request.GET.get("page")
        last = _paginate(last, page, 20)
    elif page_name == "map":
        # Return all data, lookup on mongo to be faster.
        mongo_results = db.analyses.find({"metadata.gps.pos": {"$exists": True}})
        # Get results (run a bunch of queries to avoid too long sql queries).
        last = []
        for result in mongo_results:
            try:
                analyses = Analysis.objects
                if not request.user.is_superuser:
                    analyses = analyses.filter(Q(case__owner=request.user) | Q(case__users=request.user))
                last.append(analyses.get(analysis_id=result["_id"]))
            except ObjectDoesNotExist:
                continue
    else:
        raise Exception

    # Set sidebar active tab.
    request.session["sidebar_active"] = "side-images"

    return render_to_response("analyses/images/index.html",
                              {"images": last, "pagename": page_name},
                              context_instance=RequestContext(request))

@login_required
def search(request, page_name):
    """Search analysis."""
    def validate_str(s):
        """Sanitize string.
        @param s: input string
        @return: sanitized string
        """
        return re.match("^[\w\.]+$", s) is not None

    def validate_num(num):
        """Sanitize number.
        @param s: input string
        @return: sanitized string
        """
        return re.match("^[\d\.]+$", num) is not None

    # Set sidebar active tab.
    request.session["sidebar_active"] = "side-search"

    if page_name != "form":
        query = []

        # Name filter.
        if request.GET.get("filename"):
            query.append({"file_name": {"$regex": request.GET.get("filename")}})
        # Filetype filter.
        if request.GET.get("filetype"):
            query.append({"file_type": {"$regex": request.GET.get("filetype")}})
        # Hash search.
        if request.GET.get("cipher") and request.GET.get("hash"):
            if validate_str(request.GET.get("cipher")):
                query.append({"hash.{0}".format(request.GET.get("cipher").lower()): request.GET.get("hash").lower()})
            else:
                return render_to_response("analyses/images/search.html",
                                          {"error": "Cipher format not valid."},
                                          context_instance=RequestContext(request))
        # Metadata search.
        if request.GET.get("metadata_key") and request.GET.get("metadata_value"):
            if validate_str(request.GET.get("metadata_key")):
                query.append({"metadata.{0}".format(request.GET.get("metadata_key")): {"$regex": request.GET.get("metadata_value")}})
            else:
                return render_to_response("analyses/images/search.html",
                                          {"error": "Metadata key format not valid."},
                                          context_instance=RequestContext(request))
        # Signature filter.
        if request.GET.get("signature"):
            query.append({"signatures.name": {"$regex": request.GET.get("signature")}})
        # GPS search.
        # NOTE: due to a bug in mongo the geo search must be separated. See: https://jira.mongodb.org/browse/SERVER-4572
        if request.GET.get("lat") and request.GET.get("long") and request.GET.get("dist"):
            if validate_num(request.GET.get("lat")) and validate_num(request.GET.get("long")) and validate_num(request.GET.get("dist")):
                # SON is mandatory to deliver a ordered dict to mongo, otherwise it will fail.
                query.append({"metadata.gps.pos": SON([("$near", {"Longitude": float(request.GET.get("long")), "Latitude": float(request.GET.get("lat"))}), ("$maxDistance", float(request.GET.get("dist")))])})
            else:
                return render_to_response("analyses/images/search.html",
                    {"error": "Character not allowed, allowed number and dots."},
                    context_instance=RequestContext(request))

        # Compose query.
        if len(query) == 1:
            query = query[0]
        elif len(query) > 1:
            # Conditional search.
            if request.GET.get("optionsRadios")=="or":
                query = {"$or": query}
            elif request.GET.get("optionsRadios")=="and":
                query = {"$and": query}

        # Speed up map rendering if map is requested.
        # NOTE: the "and not" part is to avoid complex $and query on GEO index.
        if page_name == "map" and not (request.GET.get("lat") or request.GET.get("long") or request.GET.get("dist")):
            query = {"$and": [query, {"metadata.gps.pos": {"$exists": True}}]}

        # Run query.
        try:
            mongo_results = db.analyses.find(query)
        except TypeError:
            return render_to_response("analyses/images/search.html",
                {"error": "Empty search."},
                context_instance=RequestContext(request))

        # Get results (run a bunch of queries to avoid too long sql queries).
        results = []
        for result in mongo_results:
            try:
                analyses = Analysis.objects
                if not request.user.is_superuser:
                    analyses = analyses.filter(Q(case__owner=request.user) | Q(case__users=request.user))
                results.append(analyses.get(analysis_id=result["_id"]))
            except ObjectDoesNotExist:
                continue

        # Pagination.
        if page_name == "list" or page_name == "thumb":
            results = _paginate(results, request.GET.get("page"), 20)
        elif page_name == "map":
            # Return all data.
            pass
        else:
            raise Exception

        # Preserve query parameters across paging.
        queries_without_page = request.GET.copy()
        if queries_without_page.has_key("page"):
            del queries_without_page["page"]

        return render_to_response("analyses/images/search_results.html",
                                  {"images": results, "pagename": page_name, "get_params": queries_without_page},
                                  context_instance=RequestContext(request))
    else:
        return render_to_response("analyses/images/search.html",
                                  context_instance=RequestContext(request))

@require_safe
@login_required
def dashboard(request):
    """Dashboard view."""

    # Set sidebar active tab.
    request.session["sidebar_active"] = "side-dashboard"

    users_count = Profile.objects.count()
    open_cases_count = Case.objects.filter(state="O").count()
    analyses_complete_count = Analysis.objects.filter(state="C").count()
    last_cases = Case.objects.filter(state="O").filter(users=request.user).order_by("-created_at")[:5]
    last_analyses = Analysis.objects.filter(state="C").filter(case__users=request.user).order_by("-created_at")[:5]
    analyses_wait_count = Analysis.objects.filter(state="W").count()
    completed_graph = Analysis.objects.filter(state="C").order_by("-created_at").extra({"created_at": "date(created_at)"}).values("created_at").annotate(counter=Count("pk"))[:30]
    waiting_graph = Analysis.objects.filter(state="W").order_by("-created_at").extra({"created_at": "date(created_at)"}).values("created_at").annotate(counter=Count("pk"))[:30]
    failed_graph = Analysis.objects.filter(state="F").order_by("-created_at").extra({"created_at": "date(created_at)"}).values("created_at").annotate(counter=Count("pk"))[:30]

    return render_to_response("users/dashboard.html",
        {
            "users_count": users_count,
            "open_cases_count": open_cases_count,
            "analyses_complete_count": analyses_complete_count,
            "last_cases": last_cases,
            "last_analyses": last_analyses,
            "analyses_wait_count": analyses_wait_count,
            "completed_graph": completed_graph,
            "waiting_graph": waiting_graph,
            "failed_graph": failed_graph
        },
        context_instance=RequestContext(request))
