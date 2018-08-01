import argparse
import datetime
import os
import re
import shutil
import sys
import subprocess

from typing import List, Optional, Tuple

from collections import namedtuple

#from io_xplane2blender.xplane_constants import *

def _make_parser()->argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Creates a clean zip build with any arbitrary build info.'\
            ' It can also change xplane_config.py, create git tags, and incorporate the test suite.\n'\
            'To run the test you\'ll need to have "another addon" called io_xplane2blender_build available to Blender.')

    version_group = parser.add_argument_group("Addon Version")
    version_group.add_argument("--major",
            type=int,
            help="Override the Blender major version (very unused!)")
    version_group.add_argument("--minor",
            type=int,
            help="Override the Blender minor version")
    version_group.add_argument("--revision",
            type=int,
            help="Override the Blender revision version")

    build_metadata_group = parser.add_argument_group("Build Metadata")
    build_metadata_group.add_argument("--build-type",
            type=str,
            choices=["dev","alpha","beta","rc"],
            help="Override CURRENT_BUILD_TYPE")
    build_metadata_group.add_argument("--build-type-version",
            type=int,
            help="Override CURRENT_BUILD_TYPE_VERSION")
    build_metadata_group.add_argument("--data-model-version",
            type=int,
            help="Override CURRENT_DATA_MODEL_VERSION with an arbitrary number (dangerous, only increment!)")
    build_metadata_group.add_argument("--build-number",
            type=int,
            help="Overrides use of current time in UTC")

    parser.add_argument("--make-overrides-permanent",
            help="Changes source files to match inputs")

    parser.add_argument("--clean",
            action="store_true",
            help="Cleans files and folders created during the build process")

    test_args_group = parser.add_argument_group(
            "Options related to running the test suite before saving the build."\
            " The build number string is always tested. When conflicted, more tests are chosen over less")
    test_args_group.add_argument("--test-level",
            type=str,
            default = "all",
            choices = ["none","fast","all"],
            help="What parts of the test suite to run. --filter in --test-args will overwrite this")

    test_args_group.add_argument("--keep-files",
            type=str,
            default = "not-ignored",
            choices = ["only-tracked","not-ignored"],
            help="Select only tracked files (enforced for build-type='rc') or any not-ignored file")

    test_args_group.add_argument("--no-zip",
            action="store_true",
            help="Does not write zip, do not clean build folder. Useful for changing version numbers easily")

    parser.add_argument("--build_folder",
            type=str,
            default="./builds",
            help="Destination for the zip file. Folders will be created if it does not exist, files will be overwritten")

    return parser

#TODO: We need an is_valid, in case the versions tests aren't run, right?
class VerData():
    '''A small completely mutable version of XPlaneHelper's VerStruct class (so we don't have to worry about importing bpy without Blender.
       Also, since the point is to manipulate code "xplane_constants.BUILD_TYPE_DEV" is stored instead of "dev",
       "xplane_constants.BUILD_NUMBER_NONE" instead of its real value'''
    def __init__(self,
            addon_version:Optional[List[str]] = None,
            build_type:Optional[str]          = None,
            build_type_version:Optional[str]  = None,
            data_model_version:Optional[str]  = None,
            build_number:Optional[str]        = None):
        self.addon_version      = addon_version
        self.build_type         = build_type
        self.build_type_version = build_type_version
        self.data_model_version = data_model_version
        self.build_number       = build_number

    @staticmethod
    def make_new_build_number():
        #Use the UNIX Timestamp in UTC 
        return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y%m%d%H%M%S")

def _change_version_info(new_version:VerData)->Optional[VerData]:
    start_folder = os.path.join(os.getcwd(),"io_xplane2blender")
    end_folder = start_folder + "_build"

    old_version = VerData()

    try:
        init_file = os.path.join(start_folder,"__init__.py")
        out_init_file_contents = [] # type: List[str]
        with open(init_file,'r',newline='\n') as in_init_file:
            for line in in_init_file:
                if '"version"' in line:
                    old_version.addon_version = re.search(r"(\d+), (\d+), (\d+)",line).groups()[:]
                    ov_av = old_version.addon_version
                    nv_av = new_version.addon_version

                    line = re.sub(r"(\d+), (\d+), (\d+)","{}, {}, {}".format(
                        nv_av[0] if nv_av[0] else ov_av[0],
                        nv_av[1] if nv_av[1] else ov_av[1],
                        nv_av[2] if nv_av[2] else ov_av[2]),line)
                    
                out_init_file_contents.append(line)

        with open(init_file,'w',newline='\n') as out_init_file:
            for line in out_init_file_contents:
                out_init_file.write(line)
    except OSError as e:
        print(e)
        return None

    try:
        xplane_config_file = os.path.join(start_folder,"xplane_config.py")
        out_config_file_contents = [] # type: List[str]
        with open(xplane_config_file, 'r') as in_config_file:
            for line in in_config_file:
                if re.match("^CURRENT_BUILD_TYPE ",line):
                    old_version.build_type = re.search("\.BUILD_TYPE_([A-Z]+)$",line).group(1).lower() # type: str
                    if new_version.build_type:
                        line = re.sub(r"\.BUILD_TYPE_[A-Z]+$",".BUILD_TYPE_"+new_version.build_type.upper(),line)

                if re.match("^CURRENT_BUILD_TYPE_VERSION ",line):
                    old_version.build_type_version = re.search(r"\d+",line).group(0)
                    if new_version.build_type_version:
                        line = re.sub(r"\d+",str(new_version.build_type_version),line)

                if re.match("^CURRENT_DATA_MODEL_VERSION ",line):
                    old_version.data_model_version = re.search(r"\d+",line).group(0)
                    if new_version.data_model_version:
                        line = re.sub(r"\d+",str(new_version.data_model_version),line)

                if re.match("^CURRENT_BUILD_NUMBER ",line):
                    search_str = 'xplane_constants.BUILD_NUMBER_NONE|"\d{14}"'
                    old_version.build_number = re.search(search_str,line).group(0)
                    if not "BUILD_NUMBER_NONE" in new_version.build_number:
                        new_version.build_number = '"'+new_version.build_number+'"'

                    line = re.sub(search_str,
                            '{}'.format(new_version.build_number),
                            line)

                out_config_file_contents.append(line)

        with open(xplane_config_file, 'w', newline='\n') as out_config_file:
            for line in out_config_file_contents:
                out_config_file.write(line)
    except OSError as e:
        print(e)
        return None
    else:
        print(old_version.addon_version)
        return old_version


def _run_tests(test_args)->None:
    '''Returns None for all good or re-raises subprocess's execption'''
    try:
        completed = subprocess.run(["python","tests.py"] + test_args)
        print(completed.stdout)
    except subprocess.CalledProcessError as e:
        raise e

def _delete_unwanted_contents(keep_files:str)->None:
    '''Deletes files and empty folders using information from git'''
    try:
        if keep_files == "only-tracked":
            sub_args = 'git ls-files -c'.split()
        elif keep_files == "not-ignored":
            sub_args = 'git ls-files --others --ignore --exclude-from=.gitignore'
        completed = subprocess.run(sub_args,stdout=subprocess.PIPE,encoding="utf-8")
    except subprocess.CalledProcessError as e:
        raise e
    else:
        files_to_consider =\
                ["./"+os.path.normpath(filepath.replace("io_xplane2blender","io_xplane2blender_build"))\
                    for filepath in completed.stdout.splitlines()\
                    if filepath.startswith('io_xplane2blender')]

        try:
            for root, dirs, filenames in os.walk('./io_xplane2blender_build', topdown=False):
                for name in filenames:
                    filepath = os.path.join(root, name)
                    if keep_files == "only-tracked":
                        should_remove = filepath not in files_to_consider
                    elif keep_files == "not-ignored":
                        should_remove = filepath in files_to_consider

                    if should_remove:
                        try:
                            os.remove(filepath)
                        except OSError as e:
                            raise e

                for name in dirs:
                    try:
                        os.rmdir(os.path.join(root, name))
                    except:
                        pass
        except OSError as e:
            raise e


def main(argv=None):
    exit_code = 0
    if argv is None:
        #TODO: Use nargs=argparse.REMAINDER?
        argv,test_args = _make_parser().parse_known_args()

    # This script requires the git directory and the tests directory
    os.chdir(os.path.dirname(__file__))
    if os.path.split(os.getcwd())[1] != 'XPlane2Blender':
        print(os.path.split(__file__)[1] +\
            " must be run in the XPlane2Blender folder! Current directory is {}"\
            .format(os.getcwd()))

    src_folder = os.path.join(os.getcwd(),"io_xplane2blender")
    build_folder = src_folder + "_build"

    # 1. Delete the old build folder, if present
    try:
        if os.path.isdir(build_folder):
            shutil.rmtree(build_folder)
    except shutil.Error as e:
        print(e)
        return 1

    if argv.clean:
        return 1

    #TODO: Make this happen inside of argparser
    build_number = str(argv.build_number) if argv.build_number else VerData.make_new_build_number()
    if len(build_number) != 14:
        print("--build_number {} is not 14 characters long".format(build_number))
        return 0

    if argv.build_type == 'rc':
        argv.keep_files = 'only-tracked'

    # 2. Parse __init__.py and xplane_config.py for version info, swap old for new
    old_version = _change_version_info(VerData(
        addon_version=list(map(lambda v: str(v) if v else None, [argv.major,argv.minor,argv.revision])),
        build_type=argv.build_type,
        build_type_version=argv.build_type_version,
        build_number=build_number))
    if not old_version:
        return 1

    #Always make sure no matter what, we replace old values for __init__.py and xplane_config
    try:
        # 3. Run any tests desired
        if argv.test_level != "none":
            try:
                _run_tests(test_args)
            except subprocess.CalledProcessError as e:
                print(e)
                return e.returncode
            except Exception as e:
                print(e)
                return 1

        # 4. Copy the source to create a new build folder
        try:
            shutil.copytree(src_folder,build_folder)
        except shutil.Error as e:
            print(e)
            return 1

        # 5. Delete temporary files, gitignore files, and (optionally) untracked files
        try:
            _delete_unwanted_contents(argv.keep_files)
        except subprocess.CalledProcessError as e:
            print(e)
            return e.returncode
        except OSError as e:
            print(e)
            return 1

        # 6. Zip up folder, rename it, move to ./builds folder
    finally:
        # 7. (if desired, which is almost always), replace old values for __init__.py and xplane_config.
        if not argv.make_overrides_permanent:
            print(old_version)
            _change_version_info(old_version)

    #8. Clean the builds folder
    try:
        if not argv.no_zip:
            shutil.rmtree(build_folder)
    except shutil.Error as e:
        print(e)
        return 1
    else:
        return 0

if __name__ == "__main__":
    sys.exit(main())
