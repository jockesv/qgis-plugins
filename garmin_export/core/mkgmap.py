"""Building and locating the mkgmap command line. Pure Python."""

import glob
import os
import shlex
import shutil

DEFAULT_JAVA = "java"


def find_java(configured=""):
    """Return a usable java executable path or None."""
    if configured:
        return configured if os.path.isfile(configured) else shutil.which(configured)
    return shutil.which(DEFAULT_JAVA)


def find_mkgmap_jar(directory):
    """Accept either the jar itself or an unpacked mkgmap folder."""
    if not directory:
        return None
    if os.path.isfile(directory):
        return directory
    for pattern in ("mkgmap.jar", "mkgmap-r*/mkgmap.jar", "*/mkgmap.jar"):
        hits = sorted(glob.glob(os.path.join(directory, pattern)))
        if hits:
            return hits[-1]
    return None


class CompileOptions(object):
    def __init__(self):
        self.map_name = "Garmin Map"
        self.family_id = 5001
        self.product_id = 1
        self.start_map_id = 63240001
        self.codepage = 1252
        self.make_gmapsupp = True
        self.make_tdb = False
        self.make_index = False
        self.typ_file = ""
        self.extra_args = ""
        self.memory_mb = 1024


def build_command(java, jar, opts, mp_files, output_dir):
    """Return the argv list that compiles ``mp_files`` into Garmin IMG files."""
    cmd = [java, "-Xmx%dm" % opts.memory_mb, "-jar", jar]
    cmd += [
        "--output-dir=%s" % output_dir,
        "--mapname=%d" % opts.start_map_id,
        "--family-id=%d" % opts.family_id,
        "--product-id=%d" % opts.product_id,
        "--family-name=%s" % opts.map_name,
        "--series-name=%s" % opts.map_name,
        "--description=%s" % opts.map_name,
    ]
    cmd.append("--unicode" if opts.codepage == 65001 else "--latin1")
    if opts.make_gmapsupp:
        cmd.append("--gmapsupp")
    if opts.make_tdb:
        cmd.append("--tdbfile")
    if opts.make_index:
        cmd.append("--index")
    if opts.extra_args.strip():
        cmd += shlex.split(opts.extra_args)
    cmd += list(mp_files)
    if opts.typ_file:
        cmd.append(opts.typ_file)
    return cmd
