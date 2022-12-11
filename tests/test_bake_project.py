import datetime
import os
import shlex
import subprocess
import sys
from contextlib import contextmanager
from typing import List

import pytest
from cookiecutter.utils import rmtree

# logging.basicConfig(level=logging.DEBUG)


_DEPENDENCY_FILE = "pyproject.toml"
_INSTALL_DEPS_COMMANDS = [
    "poetry install",
]


def build_commands(commands):
    cmds = _INSTALL_DEPS_COMMANDS.copy()
    cmds.extend(commands)
    return cmds


@contextmanager
def inside_dir(dirpath):
    """
    Execute code from inside the given directory
    :param dirpath: String, path of the directory the command is being run.
    """
    old_path = os.getcwd()
    try:
        os.chdir(dirpath)
        yield
    finally:
        os.chdir(old_path)


@contextmanager
def bake_in_temp_dir(cookies, *args, **kwargs):
    """
    Delete the temporal directory that is created when executing the tests
    :param cookies: pytest_cookies.Cookies,
        cookie to be baked and its temporal files will be removed
    """
    result = cookies.bake(*args, **kwargs)
    try:
        yield result
    finally:
        rmtree(str(result.project))


def run_inside_dir(commands, dirpath):
    """
    Run a command from inside a given directory, returning the exit status
    :param commands: Commands that will be executed
    :param dirpath: String, path of the directory the command is being run.
    """
    with inside_dir(dirpath):
        for command in commands:
            subprocess.check_call(shlex.split(command))


def check_output_inside_dir(command, dirpath):
    """Run a command from inside a given directory, returning the command output"""
    with inside_dir(dirpath):
        return subprocess.check_output(shlex.split(command))


def execute(command: List[str], dirpath: str, timeout=30, supress_warning=True):
    """Run command inside given directory and returns output

    if there's stderr, then it may raise exception according to supress_warning
    """
    with inside_dir(dirpath):
        proc = subprocess.Popen(
            command,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )

    out, err = proc.communicate(timeout=timeout)
    out = out.decode('utf-8')
    err = err.decode('utf-8')

    if err and not supress_warning:
        raise RuntimeError(err)
    else:
        print(err)
        return out

def project_info(result):
    """Get toplevel dir, project_slug, and project dir from baked cookies"""
    project_path = str(result.project)
    project_slug = os.path.split(project_path)[-1]
    project_dir = os.path.join(project_path, project_slug.replace('-', '_'))
    return project_path, project_slug, project_dir


def test_bake_with_defaults(cookies):
    with bake_in_temp_dir(cookies) as result:
        assert result.project.isdir()
        assert result.exit_code == 0
        assert result.exception is None

        found_toplevel_files = [f.basename for f in result.project.listdir()]
        assert _DEPENDENCY_FILE in found_toplevel_files
        assert 'python_boilerplate' in found_toplevel_files
        assert 'setup.cfg' in found_toplevel_files
        assert 'tests' in found_toplevel_files


def test_bake_without_author_file(cookies):
    with bake_in_temp_dir(
        cookies,
        extra_context={'create_author_file': 'n'}
    ) as result:
        found_toplevel_files = [f.basename for f in result.project.listdir()]
        assert 'AUTHORS.md' not in found_toplevel_files
        doc_files = [f.basename for f in result.project.join('docs').listdir()]
        assert 'authors.md' not in doc_files


def test_docstrings_style(cookies):
    with bake_in_temp_dir(cookies, extra_context={'docstrings_style': 'google'}) as result:
        assert result.project.isdir()
        # Test lint rule contains google style
        flake8_conf_file_apth = result.project.join("setup.cfg")
        lines = flake8_conf_file_apth.readlines()
        assert "docstring-convention = google" in ''.join(lines)


@pytest.mark.parametrize("args", [
    ({'command_line_interface': "No command-line interface"}, False),
    ({'command_line_interface': 'Click'}, True),
])
def test_bake_with_no_console_script(cookies, args):
    context, is_present = args
    result = cookies.bake(extra_context=context)
    project_path, project_slug, project_dir = project_info(result)
    found_project_files = os.listdir(project_dir)
    assert ("cli.py" in found_project_files) == is_present

    pyproject_path = os.path.join(project_path, _DEPENDENCY_FILE)
    with open(pyproject_path, 'r') as pyproject_file:
        assert ('[tool.poetry.scripts]' in pyproject_file.read()) == is_present


def test_bake_with_console_script_cli(cookies):
    context = {'command_line_interface': 'Click'}
    result = cookies.bake(extra_context=context)
    project_path, project_slug, project_dir = project_info(result)
    module_path = os.path.join(project_dir, 'cli.py')

    out = execute([sys.executable, module_path], project_dir)
    assert project_slug in out

    out = execute([sys.executable, module_path, "--help"], project_dir)

    assert 'Show this message and exit.' in out
