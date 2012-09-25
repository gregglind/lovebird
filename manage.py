import os
import sys
import xml.dom.minidom
import subprocess
import shutil
import zipfile
from ConfigParser import ConfigParser

# Path to the root of the extension, relative to where this script is
# located.
EXT_SUBDIR = "extension"

def find_profile_dir(name, app):
    """
    Given the name of a Firefox or Thunderbird profile, attempts to find the absolute
    path to its directory.  If it can't be found, None is returned.
    """

    base_path = None
    if sys.platform == "darwin":
        if app == "ff":
            base_path = os.path.expanduser( "~/Library/Application Support/Firefox/")
        elif app == "tb":
            base_path = os.path.expanduser( "~/Library/Thunderbird/")
    elif sys.platform.startswith("win"):
        # TODO: This only works on 2000/XP/Vista, not 98/Me.
        appdata = os.environ["APPDATA"]
        if app == "ff":
            base_path = os.path.join(appdata, "Mozilla\\Firefox")
        elif app == "tb":
            base_path = os.path.join(appdata, "Thunderbird")
    elif sys.platform == "cygwin":
        appdata = os.environ["APPDATA"]
        if app == "ff":
            base_path = os.path.join(appdata, "Mozilla\\Firefox")
        elif app == "tb":
            base_path = os.path.join(appdata, "Thunderbird")
    else:
        if app == "ff":
            base_path = os.path.expanduser("~/.mozilla/firefox/")
        elif app == "tb":
            base_path = os.path.expanduser("~/.thunderbird/")
    inifile = os.path.join(base_path, "profiles.ini")
    config = ConfigParser()
    config.read(inifile)
    profiles = [section for section in config.sections()
                if section.startswith("Profile")]
    for profile in profiles:
        if config.get(profile, "Name") == name:
            # TODO: Look at IsRelative?
            path = config.get(profile, "Path")
            if not os.path.isabs(path):
                path = os.path.join(base_path, path)
            print "Found profile '%s' at %s." % (name, path)
            return path
    print "Couldn't find a profile called '%s'." % name
    return None

def get_install_rdf_dom(path_to_extension_root):
    rdf_path = os.path.join(path_to_extension_root, "install.rdf")
    rdf = xml.dom.minidom.parse(rdf_path)
    return rdf

def get_install_rdf_property(path_to_extension_root, property):
    rdf = get_install_rdf_dom(path_to_extension_root)
    element = rdf.documentElement.getElementsByTagName(property)[0]
    return element.firstChild.nodeValue

def run_python_script(args):
    retval = subprocess.call([sys.executable] + args)
    if retval:
        print "Process failed with exit code %d." % retval
        sys.exit(retval)

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print "usage: %s <command>" % sys.argv[0]
        print
        print "'command' can be one of the following:"
        print
        print "    unittest - run unit tests"
        print "    test - run system and unit tests"
        print "    install - install to the given profile (firefox)"
        print "    uninstall - uninstall from the given profile (firefox)"
        print "    installtb - install to the given profile (thunderbird)"
        print "    uninstalltb - uninstall from the given profile (thunderbird)"
        print "    build-xpi - build an xpi of the addon"
        print
        sys.exit(1)

    main = __import__("__main__")
    mydir = os.path.abspath(os.path.split(main.__file__)[0])

    path_to_extension_root = os.path.join(mydir, EXT_SUBDIR)

    cmd = args[0]

    if cmd == "test":
        this_script = sys.argv[0]
        this_dir = os.path.dirname(this_script)
        print "Running unit tests."
        run_python_script([this_script, "unittest"])
        print "Running system tests."
        run_python_script([os.path.join(this_dir, "systemtests.py")])
        print "All tests successful."
    elif cmd == "unittest":
        if subprocess.call(["which", "xpcshell"],
                           stdout=subprocess.PIPE) != 0:
            print "You must have xpcshell on your PATH to run tests."
            sys.exit(1)

        xpcshell_args = [
            "xpcshell",
            "-v", "180",     # Use Javascript 1.8
            "-w",            # Enable warnings
            "-s",            # Enable strict mode
            os.path.join(mydir, "xpcshell_tests.js"),
            path_to_extension_root
            ]

        retval = subprocess.call(xpcshell_args)
        sys.exit(retval)
    elif cmd in ["install", "uninstall", "installtb", "uninstalltb"]:
        if len(args) != 2:
            print "Attempting to find location of default profile..."

            if cmd in ["install", "uninstall"]:
                profile_dir = find_profile_dir("default", "ff")
            elif cmd in ["installtb", "uninstalltb"]:
                profile_dir = find_profile_dir("default", "tb")
        else:
            profile_dir = args[1]
            if not os.path.exists(profile_dir):
                print "Attempting to find a profile with the name '%s'." % (
                    profile_dir
                    )
                if cmd in ["install", "uninstall"]:
                    profile_dir = find_profile_dir("default", "ff")
                elif cmd in ["installtb", "uninstalltb"]:
                    profile_dir = find_profile_dir("default", "tb")

        if not (profile_dir and os.path.exists(profile_dir) and
                os.path.isdir(profile_dir)):
            print "Can't resolve profile directory; aborting."
            sys.exit(1)

        extension_id = get_install_rdf_property(path_to_extension_root,
                                                "em:id")

        extension_file = os.path.join(profile_dir,
                                      "extensions",
                                      extension_id)
        files_to_remove = ["compreg.dat",
                           "xpti.dat"]
        for filename in files_to_remove:
            abspath = os.path.join(profile_dir, filename)
            if os.path.exists(abspath):
                os.remove(abspath)
        if os.path.exists(extension_file):
            if os.path.isdir(extension_file):
                shutil.rmtree(extension_file)
            else:
                os.remove(extension_file)
        if cmd in ["install", "installtb"]:
            #if cygwin, change the path to windows format so firefox can understand it
            if sys.platform == "cygwin":
                file = 'cygpath.exe -w ' + path_to_extension_root
                path_to_extension_root = "".join(os.popen(file).readlines()).replace("\n", " ").rstrip()
            
            
            fileobj = open(extension_file, "w")
            fileobj.write(path_to_extension_root)
            fileobj.close()
            print "Extension '%s' installed." % extension_id
        else:
            print "Extension '%s' uninstalled." % extension_id
    elif cmd == "build-xpi":
        version = get_install_rdf_property(path_to_extension_root,
                                           "em:version")
        extname = get_install_rdf_property(path_to_extension_root,
                                           "em:name").lower()
        zfname = "%s-%s.xpi" % (extname, version)
        zf = zipfile.ZipFile(zfname,
                             "w",
                             zipfile.ZIP_DEFLATED)
        for dirpath, dirnames, filenames in os.walk(path_to_extension_root):
            for filename in filenames:
                abspath = os.path.join(dirpath, filename)
                arcpath = abspath[len(path_to_extension_root)+1:]
                zf.write(abspath, arcpath)
        print "Created %s." % zfname
    else:
        print "Unknown command '%s'" % cmd
        sys.exit(1)
