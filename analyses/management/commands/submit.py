# Ghiro - Copyright (C) 2013 Ghiro Developers.
# This file is part of Ghiro.
# See the file 'docs/LICENSE.txt' for license terms.

import magic
import os
from django.core.management.base import BaseCommand
from optparse import make_option

from analyses.models import Case, Analysis
from users.models import Profile
from analyzer.db import save_file
from analyzer.utils import create_thumb


class Command(BaseCommand):
    """Image submission via command line."""

    option_list = BaseCommand.option_list + (
        make_option("--target", "-t", dest="target",
            help="Path of the file or directory to submit"),
        make_option("--case", "-c", dest="case",
            help="Case ID, images will be attached to it"),
        make_option("--username", "-u", dest="username",
            help="Username"),
    )

    help = "Task submission"

    def handle(self, *args, **options):
        """Runs command."""
        # Get options.
        user = Profile.objects.get(username=options["username"].strip())
        case = Case.objects.get(pk=options["case"].strip())

        # Add directory or files.
        if os.path.isdir(options["target"]):
            for file_name in os.listdir(options["target"]):
                print "INFO: processing {0}".format(file_name)
                self._add_task(os.path.join(options["target"], file_name), case, user)
        elif os.path.isfile(options["target"]):
            print "INFO: processing {0}".format(options["target"])
            self._add_task(options["target"], case, user)
        else:
            print "ERROR: target is not a file or directory"

    def _add_task(self, file, case, user):
        """Adds a new task to database.
        @param file: file path
        @param case: case id
        @param user: user id
        """
        task = Analysis()
        task.owner = user
        task.case = case
        task.file_name = os.path.basename(file)
        mime = magic.Magic(mime=True)
        task.image_id = save_file(file_path=file, content_type=mime.from_file(file))
        task.thumb_id = create_thumb(file)
        task.save()
