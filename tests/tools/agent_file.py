import io
import os
import threading
import time
from pathlib import Path
from typing import Optional, AnyStr, Generator

import docker
import docker.types


class MountedFile(io.TextIOBase):
    DEFAULT_READ_TIMEOUT = 10

    def __init__(
            self,
            container_path: str,
            host_path: Path,
            name: Optional[str] = None,
            type: str = "bind",
            mode: str = "r",
            content: Optional[AnyStr] = None
    ):
        self.container_path = container_path

        if name is None:
            name = container_path.replace(os.sep, "_")
            host_path = host_path / name

        self.host_path = host_path
        self._type = type
        self._mode = mode
        self._initial_content = content

        self._file_obj = None
        self._file_obj_lock = threading.Lock()
        self._buffer = io.StringIO()

    def create(self):
        if not self.host_path.exists():
            self.host_path.touch()
        if self._initial_content:
            self.write_content(self._initial_content)

        self._file_obj = self.host_path.open(self._mode)

    @property
    def docker_mount(self):
        return docker.types.Mount(
            str(self.container_path),
            str(self.host_path),
            type=self._type,
            consistency="consistent"
        )

    def write_content(self, data: str):
        self.host_path.write_text(data)

    def read_content(self):
        return self.host_path.read_text()

    def read(self, size: Optional[int] = ...) -> str:
        data = self._file_obj.read(size)
        self._buffer.write(data)
        return data

    def readline(self, size: int = ...) -> str:
        data = self._file_obj.readline()
        self._buffer.write(data)
        return data

    def write(self, s: str) -> int:
        n = self._file_obj.write(s)
        self._file_obj.flush()
        return n

    def writeline(self, s: str) -> int:
        return self.write(f"{s}\n")