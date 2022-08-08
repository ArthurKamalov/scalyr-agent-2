# Copyright 2014-2021 Scalyr Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import sys
import subprocess
import shlex
import logging
import os
import pathlib as pl
from typing import List

# If this environment variable is set, then commands output is not suppressed.
DEBUG = bool(os.environ.get("AGENT_BUILD_DEBUG"))

# If this env. variable is set, then the code runs inside the docker.
IN_DOCKER = bool(os.environ.get("AGENT_BUILD_IN_DOCKER"))

# If this env. variable is set, than the code runs in CI/CD (e.g. Github actions)
IN_CICD = bool(os.environ.get("AGENT_BUILD_IN_CICD"))
IN_CICD = True

# A counter for all commands that have been executed since start of the program.
# Just for more informative logging.
_COMMAND_COUNTER = 0


def init_logging():
    """
    Init logging and defined additional logging fields to logger.
    """

    # If the code runs in docker, then add such field to the log message.
    in_docker_field_format = "[IN_DOCKER]" if IN_DOCKER else ""

    logging.basicConfig(
        level=logging.INFO,
        format=f"[%(levelname)s][%(module)s:%(lineno)s]{in_docker_field_format} %(message)s",
    )


# Make shlex.join for Python 3.7
if sys.version_info < (3, 8):

    def shlex_join(cmd: List):
        return " ".join(shlex.quote(arg) for arg in cmd)

else:
    shlex_join = shlex.join


def subprocess_command_run_with_log(func):
    """
    Wrapper for 'subprocess.check_call' and 'subprocess.check_output' function that also logs
    additional info when command is executed.
    :param func: Function to wrap.
    """

    def wrapper(*args, **kwargs):

        global _COMMAND_COUNTER

        # Make info message with all command line arguments.
        cmd_args = kwargs.get("args")
        if cmd_args is None:
            cmd_args = args[0]
        if isinstance(cmd_args, list):
            # Create command string.
            cmd_str = shlex_join(cmd_args)
        else:
            cmd_str = cmd_args

        number = _COMMAND_COUNTER
        _COMMAND_COUNTER += 1
        logging.info(f" ### RUN COMMAND #{number}: '{cmd_str}'. ###")
        try:
            result = func(*args, **kwargs)
        except subprocess.CalledProcessError as e:
            logging.info(f" ### COMMAND #{number} FAILED. ###\n")
            raise e from None
        else:
            logging.info(f" ### COMMAND #{number} ENDED. ###\n")
            return result

    return wrapper


# Also create alternative version of subprocess functions that can log additional messages.
check_call_with_log = subprocess_command_run_with_log(subprocess.check_call)
check_output_with_log = subprocess_command_run_with_log(subprocess.check_output)


class DockerContainer:
    """
    Simple wrapper around docker container that allows to use context manager to clean up when container is not
    needed anymore.
    NOTE: The 'docker' library is not used on purpose, since there's only one abstraction that is needed. Using
    docker through the docker CLI is much easier and does not require the "docker" lib as dependency.
    """

    def __init__(
        self,
        name: str,
        image_name: str,
        ports: List[str] = None,
        mounts: List[str] = None,
        command: List[str] = None,
        detached: bool = True
    ):
        self.name = name
        self.image_name = image_name
        self.mounts = mounts or []
        self.ports = ports or []
        self.command = command or []
        self.detached = detached

    def start(self):

        # Kill the previously run container, if exists.
        self.kill()

        command_args = [
            "docker",
            "run",
            "-d" if self.detached else "-i",
            "--name",
            self.name,
        ]

        for port in self.ports:
            command_args.append("-p")
            command_args.append(port)

        for mount in self.mounts:
            command_args.append("-v")
            command_args.append(mount)

        command_args.append(self.image_name)

        command_args.extend(self.command)

        check_call_with_log(command_args)

    def kill(self):
        check_call_with_log(["docker", "rm", "-f", self.name])

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.kill()


class LocalRegistryContainer(DockerContainer):
    """
    Container start runs local docker registry inside.
    """

    def __init__(
        self, name: str, registry_port: int, registry_data_path: pl.Path = None
    ):
        """
        :param name: Name of the container.
        :param registry_port: Host port that will be mapped to the registry's port.
        :param registry_data_path: Host directory that will be mapped to the registry's data root.
        """
        super(LocalRegistryContainer, self).__init__(
            name=name,
            image_name="registry:2",
            ports=[f"{registry_port}:5000"],
            mounts=[f"{registry_data_path}:/var/lib/registry"],
        )
