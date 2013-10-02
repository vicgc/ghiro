# Ghiro - Copyright (C) 2013 Ghiro Developers.
# This file is part of Ghiro.
# See the file 'docs/LICENSE.txt' for license terms.

import chardet
import StringIO

from PIL import Image
from django.db.models import Q

import analyzer.db as db
from hashes.models import List

class AutoVivification(dict):
    """Implementation of perl's autovivification feature."""
    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            value = self[item] = type(self)()
            return value

    def _convert_to_dict(self, d):
        if isinstance(d, AutoVivification):
            return dict((k, self._convert_to_dict(v)) for k, v in d.items())
        return d

    def to_dict(self):
        return self._convert_to_dict(self)

class HashComparer():
    """Compares hashes with hashes lists."""
    @staticmethod
    def run(hashes, analysis):
        for key, value in hashes.iteritems():
            # Get all lists matching hash type.
            hash_lists = List.objects.filter(cipher=key).filter(Q(owner=analysis.owner) | Q(public=True))
            # Check hashes.
            for hash_list in hash_lists:
                if List.objects.filter(pk=hash_list.pk).filter(hash__value=value).exists():
                    hash_list.matches.add(analysis)

def to_unicode(str):
    """Attempt to fix non uft-8 string into utf-8. It tries to guess input encoding,
    if fail retry with a replace strategy (so undetectable chars will be escaped).
    @see: fuller list of encodings at http://docs.python.org/library/codecs.html#standard-encodings
    """

    def brute_enc(str):
        """Trying to decode via simple brute forcing."""
        result = None
        encodings = ("ascii", "utf8", "latin1")
        for enc in encodings:
            if result:
                break
            try:
                result = unicode(str, enc)
            except UnicodeDecodeError:
                pass
        return result

    def chardet_enc(str):
        """Guess encoding via chardet."""
        result = None
        enc = chardet.detect(str)["encoding"]

        try:
            result = unicode(str, enc)
        except UnicodeDecodeError:
            pass

        return result

    # If already in unicode, skip.
    if isinstance(str, unicode):
        return str

    # First try to decode against a little set of common encodings.
    result = brute_enc(str)

    # Try via chardet.
    if not result:
        result = chardet_enc(str)

    # If not possible to convert the input string, try again with
    # a replace strategy.
    if not result:
        result = unicode(str, errors="replace")

    return result

def str2image(data):
    """Converts binary data to PIL Image object.
    @param data: binarydata
    @return: PIL Image object
    """
    output = StringIO.StringIO()
    output.write(data)
    output.seek(0)
    return Image.open(output)

def image2str(img):
    """Converts PIL Image object to binary data.
    @param img: PIL Image object
    @return:  binary data
    """
    f = StringIO.StringIO()
    img.save(f, "JPEG")
    return f.getvalue()

def create_thumb(file_path):
    """Create thumbnail
    @param file_path: file path
    @return: GridFS ID
    """
    try:
        thumb = Image.open(file_path)
        thumb.thumbnail([200, 150], Image.ANTIALIAS)
        return db.save_file(data=image2str(thumb), content_type="image/jpeg")
    except:
        return None