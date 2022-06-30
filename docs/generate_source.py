#!/usr/bin/env python
from importlib import import_module
from io import StringIO
import os
from shutil import rmtree
from typing import List

DOC_TITLE = "API Reference"  # Sphinx default: "Welcome to __module__ documentation!"
ROOT_FILENAME = "index.rst"  # could be api_ref.rst to not stomp on a custom index.rst
INCLUDE_INDICIES_IN_ROOT = False  # Add default Indicies and Moudles link to this file.

ROOT_MODULE = "wkflws"
SOURCE_PATH = "../wkflws/"
DOC_BASE_PATH = "source/api_reference/"  # should have a trailing slash

IGNORED_DIR_PATTERNS: List[str] = [
    "__pycache__",
    "tests",
]
IGNORED_FILE_PATTERNS: List[str] = []


IGNORED_SUBDIR = []


IGNORED_DOC_PATHS = [
    "_static",
    "source",
]
IGNORED_DOC_FILES = [
    "conf.py",
]

if __name__ == "__main__":
    for dirpath, dirnames, filenames in os.walk(DOC_BASE_PATH, topdown=True):
        # Used to skip this dirpath iteration because it's marked as ignored
        skip = False
        for path in IGNORED_DOC_PATHS:
            if dirpath.endswith(path):
                skip = True
                break

        if skip:
            continue

        # Build the path to the source code
        pydirpath = os.path.join(SOURCE_PATH, dirpath.replace(f"{DOC_BASE_PATH}", ""))
        if not os.path.isdir(pydirpath):
            print(f"Old directory {pydirpath} removed... cleaning up {dirpath}")
            rmtree(dirpath)  # Recursively delete directory
            continue

        for filename in filenames:
            if filename == "index.rst":
                pyfilename = "__init__.py"
            else:
                pyfilename = filename.replace(".rst", ".py")
            pyfilepath = os.path.join(pydirpath, pyfilename)
            if not os.path.isfile(pyfilepath):
                filepath = os.path.join(dirpath, filename)
                print("Removing {}".format(filepath))
                os.remove(filepath)

    count = 0
    for dirpath, dirnames, filenames in os.walk(SOURCE_PATH, topdown=True):
        # Topdown will give us the root hitched directory first. This count is
        # used to write a different version of the index file containing a
        # different title and footer.
        count += 1

        # Used to skip this dirpath iteration because it is marked as something
        # to ignore.
        skip = False

        for ignored_pattern in IGNORED_DIR_PATTERNS:
            if dirpath.endswith(ignored_pattern):
                # This is a path we want to ignore
                for path in dirnames:
                    # since os.walk returns all subdirectories as 'dirpath' so
                    # append a list of subdirectories to ignore based on
                    # previous matches.
                    IGNORED_SUBDIR.append(os.path.join(ignored_pattern, path))
                skip = True
                break

        for ignored_pattern in IGNORED_SUBDIR:
            # Skip anything that's a sub directory of an IGNORED_DIR_PATTERN
            if dirpath.endswith(ignored_pattern):
                for path in dirnames:
                    # since os.walk returns all subdirectories as 'dirpath' so
                    # append a list of subdirectories to ignore based on
                    # previous matches.
                    IGNORED_SUBDIR.append(os.path.join(ignored_pattern, path))
                skip = True
                break

        if skip:
            continue

        # The source root isn't necessary at the point
        dirpath = dirpath.replace(SOURCE_PATH, "")

        # Mimic the layout of the source tree in the doc tree
        base_path = os.path.join(DOC_BASE_PATH, dirpath)

        # The title of the doc should be the name of the module
        title = os.path.basename(dirpath)

        # The base of this module. Sphinx uses the module to extra docstrings
        # and build the documentation.
        if dirpath:
            module_base = f'{ROOT_MODULE}.{dirpath.replace(os.sep, ".")}'
        else:
            # The dot will be added below for each sub-module in the root
            # source directory.
            module_base = ROOT_MODULE

        # For this path, create an index.rst
        if count == 1:
            # This is for the root module.
            title = DOC_TITLE
            index_rst_path = os.path.join(base_path, ROOT_FILENAME)
        else:
            # This is a submodule
            index_rst_path = os.path.join(base_path, "index.rst")

            # If someone added a short description in the doc string include
            # that as part of the title.
            mod = import_module(module_base)
            if mod.__doc__:
                desc = mod.__doc__.split("\n")[0]
                title = "{} - {}".format(title, desc)

        # Content container for the index.rst for this dirpath.
        index_rst = StringIO("", newline="\n")

        # Prepare the directory
        if not os.path.exists(base_path):
            os.mkdir(base_path)

        index_rst.write("{}\n".format(title))
        index_rst.write("{}\n\n".format("=" * len(title)))
        index_rst.write(".. toctree::\n")
        index_rst.write("   :maxdepth: {}\n\n".format(2 if count < 2 else 2))
        # The above line was `1 if count < 2 else 2`

        # index.rst should contain links to dirname/index.rst - Those index
        # files will be created later in the loop.
        for dirname in sorted(dirnames):
            if dirname in IGNORED_DIR_PATTERNS:
                continue
            index_rst.write("   {}/index\n".format(dirname))

        # index.rst should contain links to filename.rst & create the file
        for filename in sorted(filenames):
            # Ignore __init__.py because this translates to index.rst as well
            # as non python files.
            if (
                filename in IGNORED_FILE_PATTERNS
                or filename == "__init__.py"
                or not filename.endswith(".py")
            ):
                continue
            link = filename.replace(".py", "")
            index_rst.write("   {}\n".format(link))

            mod_rst_path = os.path.join(base_path, "{}.rst".format(link))
            mod_rst = StringIO("", newline="\n")
            module_path = "{}.{}".format(module_base, link)

            # If someone added a short description include that in the title
            submod = import_module(module_path)
            if submod.__doc__:
                desc = submod.__doc__.split("\n")[0]
                title = "{} - {}".format(link, desc)
            else:
                title = link

            mod_rst.write("{}\n".format(title))
            mod_rst.write("{}\n\n".format("=" * len(title)))
            mod_rst.write(".. automodule:: {}\n".format(module_path))
            mod_rst.write("   :members:\n")
            mod_rst.write("   :undoc-members:\n")
            mod_rst.write("   :special-members: __init__\n")
            print("> {}".format(mod_rst_path))
            with open(mod_rst_path, "w") as f:
                f.write(mod_rst.getvalue())

        if count == 1 and INCLUDE_INDICIES_IN_ROOT:
            # Add handy links to the root index.rst
            index_rst.write("\nIndices and tables\n")
            index_rst.write("==================\n\n")
            index_rst.write("* :ref:`genindex`\n")
            index_rst.write("* :ref:`modindex`\n")
            pass
        else:
            index_rst.write("\n.. automodule:: {}\n".format(module_base))
            index_rst.write("   :members:\n")
            index_rst.write("   :undoc-members:\n")

        print("> {}".format(index_rst_path))
        with open(index_rst_path, "w") as f:
            f.write(index_rst.getvalue())
