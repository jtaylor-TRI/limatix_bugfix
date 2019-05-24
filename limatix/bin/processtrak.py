#! /bin/env python
from __future__ import print_function

import sys

orig_sys_exit=sys.exit # keep a copy of real sys.exit, because ipython messes it up

# set up stdout/stderr forwarders as FIRST step before other modules get loaded

from limatix.processtrak_stdiocapture import stdiohandler

stdouthandler=stdiohandler(sys.stdout,None)
sys.stdout=stdouthandler

stderrhandler=stdiohandler(sys.stderr,None)
sys.stderr=stderrhandler

import os
import os.path
import posixpath
import socket
import copy
import inspect
import numbers
import traceback
import collections
import ast
import hashlib
import binascii

from pkg_resources import resource_string
from lxml import etree

try:
    from cStringIO import StringIO
    pass
except ImportError:
    from io import StringIO
    pass

if "--gtk3" in sys.argv or sys.version_info[0] >= 3:  # gtk3
    import gi
    gi.require_version('Gtk','3.0')
    from gi.repository import Gtk as gtk
    pass
else :  # gtk2
    import gobject
    import gtk
    pass

import shutil
import datetime
import subprocess

try:
    # py2.x
    from urllib import pathname2url
    from urllib import url2pathname
    from urllib import quote
    from urllib import unquote
    from urlparse import urlparse
    from urlparse import urlunparse
    from urlparse import urljoin    
    pass
except ImportError:
    # py3.x
    from urllib.request import pathname2url
    from urllib.request import url2pathname
    from urllib.parse import quote
    from urllib.parse import unquote
    from urllib.parse import urlparse
    from urllib.parse import urlunparse
    from urllib.parse import urljoin
    pass

from limatix import lm_units
lm_units.units_config("insert_basic_units")
from limatix import timestamp
from limatix import canonicalize_path
from limatix.canonicalize_path import etxpath2human

#class dummy(object):
#    pass

## trace symbolic link to find installed directory
#thisfile=sys.modules[dummy.__module__].__file__
#if os.path.islink(thisfile):
#    installedfile=os.readlink(thisfile)
#    if not os.path.isabs(installedfile):
#        installedfile=os.path.join(os.path.dirname(thisfile),installedfile)
#        pass
#    pass
#else:
#    installedfile=thisfile
#    pass
#
#installeddir=os.path.dirname(installedfile)
#
#if os.path.exists(os.path.join(installeddir,"../lib/checklist.py")):
#    installeddir=os.path.join(installeddir,"../")
#    pass
#elif os.path.exists(os.path.join(installeddir,"../gui2/lib/checklist.py")):
#    installeddir=os.path.join(installeddir,"../gui2")
#    pass
#
#sys.path.append(installeddir)
#sys.path.append(os.path.join(installeddir,"lib/"))

from limatix import dc_value as dcv
from limatix import provenance as provenance
from limatix import xmldoc
from limatix import processtrak_prxdoc
from limatix import processtrak_common
from limatix import processtrak_procstep


# Concept
# 1. Merge xmlfilter functionality into xmldoc functionality. 
#    a. Ability to define filters that can be executed
#    b. Filter must say what elements it operates on
#    c. Must be possible to further restrict which element is operated
#    d. Filter must overwrite pre-existing output
#    e. Filter must log provenance. 
#    f. Must lock output file to prevent conflicts by multiple simultaneous
#       scripts
#
#    g. Filters are defined by ".prx" files. See ../doc/prxexample.prx
#
#    h. Processing instructions are defined by an ordered list of filters
#    i. To run a filter, it must be on the list in the prx file as a "step"
#    j. A filter can be run with additional constraints so that it only 
#       operates on a subset of the usual tags. (see the -f option, below)
#    k. As the filter executes,  all elements referenced and all elements
#       created/modified are tracked so the former can be listed as 
#       <lip:used> in the <lip:process> domain and the latter can reference
#       the <lip:process> domain by uuid. 
#    l. The execution of the filter creates a new <lip:process> domain within
#       the <lip:process> domain for the execution of the processtrak program.
#       Additional sub-process domains are created for each element processed
#       by the filter. 
#    m. Once file locking support is implemented in xmldoc, critical regions
#       are defined here, and element persistence across critical regions is 
#       eliminated, it should be possible to have multiple processes running
#       simultaneously on the same file!




def usage():
    print ("""Usage: %s [-s step1name] [-s step2name]  [-a] [-d] [-p dir] [-l xpathconstraint1] [-l xpathconstraint2] [-f inputfile] ... process.prx
process.prx specifies processing steps.
      
Flags:
  -s                  Run only listed steps (multiple OK)
  -a                  Run all steps
  -d                  Drop into debugger in case of exception executing step
  -f                  Operate only on the specified input files (multiple OK)
  -l                  Apply additional xpath filters (multiple OK)
  -i                  Use ipython interactive mode to execute script
  --git-add           Stage changes to .prx and input files for commit
  --gtk3              Use GTK3 if gui elements required
  --steps             Don't do anything; just list available steps
  --status            Don't do anything; Show status of steps
  --files             Don't do anything; just list available files
    """)
    pass


def main(args=None):
    if args is None:
        args=sys.argv
        pass
    
    argv_inputfiles=set([])

    overall_starttime=timestamp.now().isoformat()


    argc=1
    positionals=[]
    stepnames=[]
    filters=[]
    allsteps=False
    liststeps=False
    listfiles=False
    status=False
    debugmode=False
    ipythonmodelist=[False] # ipythonmode is contained within a list so it is mutable by functions and these changes will be persistent
    
    while argc < len(args):
        arg=args[argc]
        
        if arg=="-s":  # -s <step>: Only run this (or these) steps
            stepnames.append(args[argc+1])
            argc+=1
            pass
        elif arg=="--steps": # just list steps
            liststeps=True
            pass
        elif arg=="-l": # -l <filter>: Apply additional filtering constraint 
                        # to elements operated on 
            filters.append(args[argc+1])
            argc+=1
            pass
        elif arg=="-f": # -f <inputfile>: Operate only on the specified file
            argv_inputfiles.add(args[argc+1])
            argc+=1
            pass
        elif arg=="--files": # just list files
            listfiles=True
            pass
        elif arg=="--status":
            status=True
            pass        
        elif arg=="-a": # run all steps
            allsteps=True
            pass
        elif arg=="-i": # enable ipython qtconsole mode
            ipythonmodelist.pop()
            ipythonmodelist.append(True)
            pass
        elif arg=="-d": # enable debugging mode
            debugmode=True
            pass
        elif arg=='--gtk3':
            # handled at imports, above
            pass
        #elif arg=="-p":  # insert path into search path for steps
        #    processtrak_procstep.steppath.insert(1,args[argc+1])
        #    argc+=1
        #    pass
        elif arg=='-h' or arg=="--help":
            usage()
            sys.exit(0)
            pass
        elif arg[0]=='-':
            raise ValueError("Unknown command line switch %s" % (arg))
        else :
            positionals.append(arg)
            pass
        argc+=1
        pass
        
    if len(positionals) > 1:
        raise ValueError("Too many positional parameters (see -h for command line help")

    if len(positionals) < 1: 
        usage()
        sys.exit(0)
        pass
        
        
    prxfile=positionals[0]
    prxfilehref=dcv.hrefvalue(prxfile,contexthref=dcv.hrefvalue("."))

    
    
    # prxdoc is loaded into memory once, so we don't use locking on it. 
    prxdoc=xmldoc.xmldoc.loadhref(prxfilehref,nsmap=processtrak_common.prx_nsmap,readonly=True,use_locking=False,debug=True)  #!!!*** Should turn debug mode off eventually... it will speed things up
    # prxdoc.merge_namespace("prx",)
    assert(prxdoc.gettag(prxdoc.getroot())=="prx:processinginstructions")


    # See if a specific hostname was specified
    hostname=prxdoc.xpathsinglestr("prx:hostname",default=None)

    if hostname is not None and hostname.split(".")[0] != provenance.determinehostname().split(".")[0]:
        sys.stderr.write("Hostname mismatch: %s in <prx:hostname> tag vs. this computer is %s.\nPlease adjust <prx:hostname> tag to match if you really want to run on this computer.\nRemove <prx:hostname> completely if this should be allowed to run on any computer.\n" % (hostname.split(".")[0],provenance.determinehostname().split(".")[0]))
        sys.exit(1)
        pass

        
    if allsteps or liststeps:
        steps=[ None ] + prxdoc.xpath("prx:step")
        pass
    else: # Convert list of step names into list of step elements
        steps=[ processtrak_prxdoc.findstep(prxdoc,stepname) for stepname in stepnames ]
        pass

    if liststeps: 
        print("")
        print("List of steps for -s option")
        print("---------------------------")
        for step_el in steps:
            if step_el is None:   # "None" means the copyinput step 
                print("copyinput      (WILL OVERWRITE CURRENT OUTPUT)")
                pass
            else:
                print(processtrak_prxdoc.getstepname(prxdoc,step_el))
                pass
            pass

        sys.exit(0)
        pass  


    inputfiles_with_hrefs=processtrak_common.getinputfiles(prxdoc)

    
        
    if listfiles:
        print("")
        print("List of files for -f option")
        print("---------------------------")
        for (inputfile,inputfilehref) in inputfiles_with_hrefs:
            print(inputfilehref.getpath())
            pass
        
        sys.exit(0)
        pass


    for argv_inputfile in argv_inputfiles:
        if argv_inputfile not in [ inputfilehref.getpath() for (inputfile,inputfilehref) in inputfiles_with_hrefs ]:
            sys.stderr.write("Specified input file %s is not listed in %s\nTry listing available files with --files.\n" % (argv_inputfile,prxfilehref.absurl()))
            sys.exit(1)
            pass
        pass
    # inputfile = prxdoc.xpathsinglestr("prx:inputfile")


    # If any input files are specified on the command line, use only
    # those input files

    
    useinputfiles_with_hrefs = [ (inputfile,inputfile_href) for (inputfile,inputfile_href) in inputfiles_with_hrefs if len(argv_inputfiles)==0 or inputfile_href.getpath() in argv_inputfiles ]

    
    
    # Build dictionary by input file of output files
    outputdict=processtrak_common.build_outputdict(prxdoc,inputfiles_with_hrefs)


    if status:
        print("")
        
        print("Step status")
        print("---------------------------")
        for (inputfile,inputfile_href) in useinputfiles_with_hrefs:
            print(" ")

            outdoc = outputdict[inputfile_href]
            # NOTE: calling open_or_lock_output with readonly=True means it's NOT OK
            # to actually execute anything with this outdoc in the outputdict, as
            # the output will be only opened as read-only
            if os.path.exists(outdoc.outputfilehref.getpath()):
                processtrak_common.open_or_lock_output(prxdoc,outdoc,None,copyfileinfo=None,readonly=True)
                xlpdocu=outdoc.output
                pass
            else:
                xlpdocu=None
                pass

            if xlpdocu is not None:
                # Find all lip:process tags with an action child that also have-- either themselves or and ancestor -- a wascontrolledby with a lip:prxfile 
                actionprocesses=xlpdocu.xpath("lip:process/descendant-or-self::lip:process[lip:action and (ancestor-or-self::lip:process/lip:wascontrolledby)[1]/lip:prxfile/@xlink:href]")
                
                actionprocs_with_prxfile=[ (actionproc,xlpdocu.xpathsinglecontext(actionproc,"(ancestor-or-self::lip:process/lip:wascontrolledby)[1]/lip:prxfile")) for actionproc in actionprocesses ]

                actionprocs_with_prxfilehref=[ (actionproc, dc_value.hrefvalue.fromxml(xlpdocu,prxfile)) for (actionproc,prxfile) in actionprocs_with_prxfile ]

                actionprocs_matching_prxfile = [ actionproc for (actionproc,actionprxfilehref) in actionprocs_with_prxfilehref if actionprxfilehref==prxfilehref ]
                actionprocs_not_matching_prxfile = [ actionproc for (actionproc,actionprxfilehref) in actionprocs_with_prxfilehref if not(actionprxfilehref==prxfilehref) ]

                actionproc_listdict_matching_prxfile = { }  # dictionary by step name of lists of actionprocs 
                for actionproc in actionprocs_matching_prxfile:
                    stepname = xlpdocu.xpathsinglecontextstr(actionproc,"lip:action")
                    if stepname not in actionproc_listdict_matching_prxfile:
                        actionproc_listdict_matching_prxfile[stepname] = [] # empty list
                        pass
                    
                    actionproc_listdict_matching_prxfile[stepname].append(actionproc)
                    pass


                # sort lists in actionproc_listdict_matching_prxfile[stepname] by starttimestamp
                
                for stepname in actionproc_listdict_matching_prxfile:  # dictionary by step name of lists of actionprocs
                    actionproc_listdict_matching_prxfile[stepname].sort(key = lambda actionproc: xlpdocu.xpathsinglecontextstr(actionproc,"lip:startimestamp"))
                    pass

                # reduce actionproc_listdict_matching_prxfile to most recent runs (last entries)
                actionproc_dict_matching_prxfile = { stepname: actionproc_listdict_matching_prxfile[stepname][-1] for stepname in actionproc_listdict_matching_prxfile }

                actionproc_date_status_dict_matching_prxfile = { stepname: (actionproc_dict_matching_prxfile[stepname], # actionproc
                                                                            xlpdocu.xpathsinglecontextstr(actionproc_dict_matching_prxfile[stepname],"lip:starttimestamp"), # start timestamp
                                                                            len(xlpdocu.xpathcontext(actionproc_dict_matching_prxfile[stepname],"descendent-or-self::lip:log[status != 'success']")) > 0 or len(xlpdocu.xpathcontext(actionproc_dict_matching_prxfile[stepname],"descendent-or-self::lip:process[count(lip:finishtimestamp) = 0]")) > 0,  # failure indicator: status not listed as success or no finish timestamp
                                                                            "-l" in ast.literal_eval(xmldocu.xpathsinglecontextstr(actionproc_dict_matching_prxfile[stepname],"lip:argv")))  # Presence of additional xpath filters when running this step
                                                                 for stepname in actionproc_listdict_matching_prxfile }
                
                
                                                                        
                                                                        
                
                pass
            else:
                actionprocs_with_prxfile = []
                pass
            
            print("Input file: %s" % (inputfile))
            print("---------------------------")
            for step_el in steps:
                if step_el is None:   # "None" means the copyinput step
                    stepname="copyinput"
                    pass
                else:
                    stepname=processtrak_prxdoc.getstepname(prxdoc,step_el)
                    pass
                if xlpdocu is None:
                    print("%20s NOT EXECUTED" % (stepname))
                    pass
                else:
                    # have an xlp document

                    if stepname not in actionproc_date_status_dict_matching_prxfile:
                        print("%20s NOT EXECUTED" % (stepname))
                        pass
                    else:
                        # did find step
                        (actionproc,date,failure,filterflag) = actionproc_date_status_dict_matching_prxfile[stepname]
                        flagstr=""
                        if failure:
                            flagstr += " FAILURE"
                            pass
                        if filterflag:
                            flagstr +=" USED_XPATH_FILTERS"
                            pass
                        
                        print("%20s %36s %s" % (stepname,date,flagstr))

                        del actionproc_date_status_dict_matching_prxfile[stepname] # mark as shown
                        pass
                    pass
                
                pass

            if len(actionproc_date_status_dict_matching_prxfile.keys()) > 0:
                print(" ")
                print("Additional steps not found in .prx file")
                print("---------------------------------------")

                for stepname in actionproc_date_status_dict_matching_prxfile:
                    print("%20s" % (stepname))
                    pass
                pass

            if len(actionprocs_not_matching_prxfile) > 0:
                print(" ")
                print("Additional steps from different .prx file")
                print("---------------------------------------")
                
                for actionproc in actionprocs_not_matching_prxfile:
                    stepname = xlpdocu.xpathsinglecontextstr(actionproc,"lip:action")
                    print("%20s" % (stepname))
                    pass
                
                
                pass
            
            pass
        
        
        sys.exit(0)
        pass


    if len(steps)==0:
        print("Nothing to do! (try specifying a step with -s <step> or all steps with -a);\nlist steps with --steps\n")
        sys.exit(0)
        pass

    #print("steps=%s" % str(steps))

    
    # Run the specified steps, on the specified files
    processtrak_common.outputdict_run_steps(prxdoc,outputdict,useinputfiles_with_hrefs,steps,filters,overall_starttime,debugmode,stdouthandler,stderrhandler,ipythonmodelist)    

    
    pass
