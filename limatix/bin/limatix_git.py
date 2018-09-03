import sys
import subprocess
import os
import os.path

try:
    # py2.x
    from urllib import pathname2url
    from urllib import url2pathname
    from urllib import quote
    from urllib import unquote
    pass
except ImportError:
    # py3.x
    from urllib.request import pathname2url
    from urllib.request import url2pathname
    from urllib.parse import quote
    from urllib.parse import unquote
    pass



from limatix import dc_value

from limatix import processtrak_cleanup



try:
    import git
    from git import Repo
    pass
except ImportError:
    raise ImportError("GitPython must be installed in order to use limatix-git")


def git_dir_context(repo):
    rootpath = repo.git.rev_parse("--show-toplevel")
    #cdup = repo.git.rev_parse("--show-cdup")  # gitpython --show-cdup doesn't work... do it with a pipe!
    # (That's because gitpython interprets all files as being in
    # the context of the rootpath)
    cdup=subprocess.Popen(["git","rev-parse","--show-cdup"],stdout=subprocess.PIPE).communicate()[0].strip().decode('utf-8')
    if len(cdup)==0:
        cdup='.'
        pass
    if cdup.endswith(os.path.sep):
        cdup=cdup[:-1]
        pass

    prefix=subprocess.Popen(["git","rev-parse","--show-prefix"],stdout=subprocess.PIPE).communicate()[0].strip().decode('utf-8')
    if len(prefix)==0:
        prefix='.'
        pass
    if prefix.endswith(os.path.sep):
        prefix=prefix[:-1]
        pass

    return (rootpath,cdup,prefix)

def add_usage():
    print("""Usage: %s add [-h] [-a] [--dry-run] <inputfiles...>
Stage modified and new raw data/script files for commit
   -h                This help
   -a                Search for .xlg, .prx, and .py files within
                     current directory to add
   --dry-run         Do not actually perform the changes
   
NOTE: This is intended for raw data, experiment logs, scripts and instructions,
      and will only stage files for a branch that does NOT contain "processed"
      in its name
""" % (sys.argv[0]))
    pass

def get_unprocessed(input_file_hrefs):
    input_files=processtrak_cleanup.infiledicts.fromhreflist(input_file_hrefs)

    (completed_set,desthref_set,href_set)=processtrak_cleanup.traverse(input_files,recursive=True,need_href_set=True,include_processed=False)

    allpaths_no_dest = [ href.getpath() for href in (completed_set | href_set)-desthref_set ]
    xlppaths = [ path for path in allpaths_no_dest if os.path.splitext(path)[1].lower()==".xlp" ]
    unprocessedpaths = [ path for path in allpaths_no_dest if os.path.splitext(path)[1].lower()!=".xlp" ]

    return (unprocessedpaths,xlppaths)

def get_processed(input_file_hrefs_unprocessed,input_file_hrefs):
    input_files_up=processtrak_cleanup.infiledicts.fromhreflist(input_file_hrefs_unprocessed)


    
    (unprocessed_completed_set,unprocessed_desthref_set,unprocessed_href_set)=processtrak_cleanup.traverse(input_files_up,recursive=True,need_href_set=True,include_processed=False)

    input_files_pr=processtrak_cleanup.infiledicts.fromhreflist(input_file_hrefs)

    (completed_set,desthref_set,href_set)=processtrak_cleanup.traverse(input_files_pr,recursive=True,need_href_set=True,include_processed=True)

    import pdb
    pdb.set_trace()
    
    processed_href_set = (completed_set | href_set) - (unprocessed_completed_set | unprocessed_href_set) - desthref_set

    processedpaths = [ href.getpath() for href in processed_href_set ]

    #import pdb
    #pdb.set_trace()
    return (processedpaths)

def filename_is_xlg_prx_py(filename):
    ext=os.path.splitext(filename)[1].lower()
    return ext==".xlg" or ext==".prx" or ext==".py"

def find_recursive_xlg_prx_py(rootpath):
    pathlist=[]
    
    for (dirpath,dirnames,filenames) in os.walk(rootpath):
        pathlist.extend([ os.path.join(dirpath,filename) for filename in filenames if filename_is_xlg_prx_py(filename) ])
        pass
    
    return pathlist
        


def add(args):
    argc=0
    positionals=[]
    all=False
    dryrun=False
    
    while argc < len(args):
        arg=args[argc]

        if arg=='-a':
            all=True
            pass
        elif arg=='-h' or arg=="--help":
            add_usage()
            sys.exit(0)
        elif arg=="--dry-run":
            dryrun=True
            pass
        elif arg.startswith('-'):
            raise ValueError("Unknown parameter: \"%s\"" % (arg))
        else:
            positionals.append(arg)
            pass
        argc+=1
        pass
        
        
    repo=Repo(".",search_parent_directories=True)

    (rootpath,cdup,prefix)=git_dir_context(repo)
    
    

    if "processed" in repo.active_branch.name:
        sys.stderr.write("Will not add raw input files/scripts/etc. to processed\nbranch.\nSwitch branches with \"git checkout\" first!\n")
        sys.exit(1)
        pass

    to_consider=[ os.path.join(prefix,positional) for positional in positionals ]
    
    if all:
        autofound_files = find_recursive_xlg_prx_py(rootpath)

        to_consider.extend(autofound_files)
        
        pass

    input_file_hrefs=[ dc_value.hrefvalue(pathname2url(input_file_name),contexthref=dc_value.hrefvalue(pathname2url(rootpath))) for input_file_name in to_consider ]
    (unprocessedpaths,xlppaths)=get_unprocessed(input_file_hrefs)

    print("Adding paths for commit:")
    for unprocessedpath in unprocessedpaths:
        print("   %s" % (unprocessedpath))
        pass
    print(" ")
    if not dryrun:
        repo.git.add(unprocessedpaths)
        pass

    if len(xlppaths) > 0:
        print("Omitted processed output:")
        for xlppath in xlppaths:
            print("   %s" % (xlppath))
            pass
        pass
    
    print("\nNow run \"git commit\"")
    pass

def add_processed_usage():
    print("""Usage: %s add-processed [-h] [-a] [--dry-run] <inputfiles...>
Stage modified and new processing output files for commit.
These should only be committed to a branch with "processed" in 
the name.
   -h                This help
   -a                Search for .xlg, .prx, and .py files within
                     current directory to add
   --dry-run         Do not actually perform the changes
   
NOTE: This is intended for processing output only,
      and will only stage files for a branch that DOES contain "processed"
      in its name.
""" % (sys.argv[0]))
    pass


def add_processed(args):
    argc=0
    positionals=[]
    all=False
    dryrun=False
    
    while argc < len(args):
        arg=args[argc]

        if arg=='-a':
            all=True
            pass
        elif arg=='-h' or arg=="--help":
            add_processed_usage()
            sys.exit(0)
        elif arg=="--dry-run":
            dryrun=True
            pass
        elif arg.startswith('-'):
            raise ValueError("Unknown parameter: \"%s\"" % (arg))
        else:
            positionals.append(arg)
            pass
        argc+=1
        pass
        
        
    repo=Repo(".",search_parent_directories=True)

    (rootpath,cdup,prefix)=git_dir_context(repo)

    to_consider=[ os.path.join(prefix,positional) for positional in positionals ]
    
    autofound_files = find_recursive_xlg_prx_py(rootpath)
    to_consider_unprocessed = to_consider + autofound_files
    
    if all:
        to_consider.extend(autofound_files)
        pass
    
    input_file_hrefs_unprocessed=[ dc_value.hrefvalue(pathname2url(input_file_name),contexthref=dc_value.hrefvalue(pathname2url(rootpath))) for input_file_name in to_consider_unprocessed ]

    input_file_hrefs=[ dc_value.hrefvalue(pathname2url(input_file_name),contexthref=dc_value.hrefvalue(pathname2url(rootpath))) for input_file_name in to_consider ]
    
    (unprocessedpaths,xlppaths)=get_unprocessed(input_file_hrefs_unprocessed)

    # Check that all unprocessedpaths are unmodified
    unprocessedabspaths = [os.path.abspath(unprocessedpath) for unprocessedpath in unprocessedpaths ]
    if len(unprocessedabspaths) > 0:

        modified_unprocessed=repo.index.diff(None,paths=unprocessedabspaths)
        if len(modified_unprocessed) > 0:
            sys.stderr.write("Modifed raw input files present:\n")
            for diff in modified_unprocessed:
                fname=diff.a_path
                sys.stderr.write("   %s\n" % (fname))
                pass
            sys.stderr.write("\nAdd these to non-processed branch with limatix-git add;git commit\n")
            sys.exit(1)
            pass

        # Check for unprocessedabspaths that match untracked files.
        # Sort paths out by filename so that we can relatively
        # quickly match them with samepath()
        untracked_byname = {}
        for untracked in repo.untracked_files:
            untracked_fname=os.path.split(untracked)[1]
            if not untracked_fname in untracked_byname:
                untracked_byname[untracked_fname]=[]
                pass
            untracked_byname[untracked_fname].append((untracked,os.path.join(rootpath,untracked)))
            pass
        
            
        unprocessed_byname = { }
        for unprocessed in unprocessedabspaths:
            unprocessed_fname=os.path.split(unprocessed)[1]
            if not unprocessed_fname in unprocessed_byname:
                unprocessed_byname[unprocessed_fname]=[]
                pass
            unprocessed_byname[unprocessed_fname].append(unprocessed)
            pass
        # Find matches between the two
        commonnames = frozenset(untracked_byname.keys()).intersection(frozenset(unprocessed_byname.keys()))

        untracked_unprocessed=[]
        for commonname in commonnames:
            for (untracked,untracked_fullpath) in untracked_byname[commonname]:
                for unprocessed in unprocessed_byname[commonname]:
                    if (os.path.samepath(untracked_fullpath,unprocessed)):
                        if len(untracked_unprocessed)==0:
                            sys.stderr.write("Untracked raw input files present:\n")
                            pass
                        untracked_unprocessed.append(untracked)
                        sys.stderr.write("   %s\n" % (untracked))
                        pass
                    pass
                pass
            pass
        if len(untracked_unprocessed) > 0:
            sys.stderr.write("\nAdd these to non-processed branch with limatix-git add;git commit\n")
            sys.exit(0)
        
        
        pass
    
    if not "processed" in repo.active_branch.name:
        sys.stderr.write("Will not add processed output to\nbranch without \"processed\" in its name.\nSwitch to a different branch with \"git checkout\" or Create a\nnew branch with \"git checkout -b\" to store\nprocessed output first!\n")
        sys.exit(1)
        pass

    processedpaths=get_processed(input_file_hrefs_unprocessed,input_file_hrefs)

    print("Adding paths for commit:")
    for processedpath in processedpaths:
        print("   %s" % (processedpath))
        pass
    print(" ")
    if not dryrun:
        repo.git.add(processedpaths)
        pass
    print("\nNow run \"git commit\"")
    pass

def init_usage():
    print("""Usage: %s init [-h] [--dry-run]
Create a new repository at this location, adding a suitable .gitignore file
   -h                This help
   --dry-run         Do not actually perform the changes
""" % (sys.argv[0]))
    pass


def init(args):
    argc=0
    positionals=[]
    all=False
    dryrun=False
    
    while argc < len(args):
        arg=args[argc]

        if arg=='-h' or arg=="--help":
            init_usage()
            sys.exit(0)
        elif arg=="--dry-run":
            dryrun=True
            pass
        elif arg.startswith('-'):
            raise ValueError("Unknown parameter: \"%s\"" % (arg))
        else:
            positionals.append(arg)
            pass
        argc+=1
        pass
        
    if len(positionals) > 0:
        raise ValueError("Unknown parameter: \"%s\"" % (positionals[0]))

    if not dryrun:
        pass

    existingrepo=True
    try:
        repo=Repo(".",search_parent_directories=True)
        pass
    except git.exc.InvalidGitRepositoryError:
        existingrepo=False
        pass

    if existingrepo:
        raise ValueError("Existing git repo already found in current directory or ancestor")

    if os.path.exists(".gitignore"):
        raise ValueError(".gitignore file already exists")

    if not dryrun:
        repo=Repo.init(".")
        pass

    if not dryrun:
        gitignore=open(".gitignore","w")
        gitignore.write(".*.bak*\n")
        gitignore.write("*~\n")
        gitignore.write("*.bak\n")
        gitignore.write("*.pyc\n")
        gitignore.close()

        repo.git.add(['.gitignore'])
        pass

    print("Repository created; now run \"git commit\" to commit the .gitignore\nThen run \"limatix-git add\" to add your raw data and scripts")
    rootpath = repo.git.rev_parse("--show-toplevel")
    pass


def usage():
    print("""Usage: %s [-h] command <command args...>
   -h                This help
Commands:
   init              Init new repo in this directory. Automatically create 
                     .gitignore
   add               Add input, data, and/or script files to repo
   add-processed     Add processed output to repo branch

---

Usual workflow: 
   git init            # Create repository (master branch)
   limatix-git add -a  # Stage raw data, manual files
   git add ...         # Manually stage additional files
   git commit          # Commit raw data and manual files to master
   # Now develop processing scripts (.prx file, etc.) 
   # During development keep commiting script changes with
   limatix-git add -a 
   # As your code gets mature, you can clean up the output trees
   # with pt_cleanup -b -p -d <prxfile.prx>
   # you should check provenance with 
   pt_checkprovenance <explog.xlp>
   # When keepable/publishable output is ready, stage it with
   git checkout -b processed_XXXXX 
   # where XXXXX represents the purpose (particular presentation, 
   # paper, etc.) 
   # Then 
   limatix-git add-processed
   # Make sure all files have been properly pulled in with
   git status
   # (if not, your processing scripts are probably failing to add 
   # hrefs to the processed experiment log, and you should switch back
   # to the data (master) branch and fix them and reprocess)
   # Also you should verify that 
   pt_cleanup -d <prxfile.prx>
   # doesn't do anything 
   # Once you are satisfied: 
   git commit
   # You can then switch back and forth between the clean tree
   # and the processed output with git checkout. 
   # Script development should generally go in the master branch, 
   # but master should be kept clean from processed output

""" % (sys.argv[0]))
    pass

def main(args=None):
    if args is None:
        args=sys.argv
        pass

    add_inputfiles=set([])

    argc=1
    
    while argc < len(args):
        arg=args[argc]

        if arg=='add':
            add(args[argc+1:])
            sys.exit(0)
            pass
        elif arg=='add-processed':
            add_processed(args[argc+1:])
            sys.exit(0)
            pass
        elif arg=='init':
            init(args[argc+1:])
            sys.exit(0)
            pass
        elif arg=='-h' or arg=="--help":
            usage()
            sys.exit(0)
            pass
        argc+=1
        pass
    usage()
    pass

