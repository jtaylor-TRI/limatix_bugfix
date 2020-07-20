import sys
import os
import os.path

try:
    # py2.x
    from urllib import pathname2url
    pass
except ImportError:
    # py3.x
    from urllib.request import pathname2url
    pass


class dummy(object):
    pass


pkgpath = sys.modules[dummy.__module__].__file__
pkgdir=os.path.split(pkgpath)[0]

def getptstepurlpath():

    return [ pathname2url(os.path.join(pkgdir,"pt_steps")) ]

def getchecklisturlpath():

    return [ pathname2url(os.path.join(pkgdir,"limatix_checklists")) ]


def getconfigurlpath():

    return [ pathname2url(os.path.join(pkgdir,"limatix_conf")) ]


versionpath = os.path.join(pkgdir,"version.txt")
if os.path.exists(versionpath):
    versionfh = open(versionpath,"r")
    __version__=versionfh.read().strip()
    versionfh.close()
    pass
else:
    __version__="UNINSTALLED"
    pass

