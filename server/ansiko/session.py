"""A PTY process whose output is copied to the display socket.

Linux only, like the daemon. The PTY is always sized to the display's grid,
never to the terminal that happened to start the session.
"""

from __future__ import annotations

import asyncio
import errno
import fcntl
import os
import pty
import signal
import struct
import termios
import threading
from collections.abc import Callable


class Session:
    def __init__(
        self,
        argv: list[str],
        cols: int,
        rows: int,
        on_output: Callable[[bytes], None],
        on_exit: Callable[[int], None],
        cwd: str | None = None,
    ) -> None:
        self.argv = argv
        self.cols = cols
        self.rows = rows
        self.on_output = on_output
        self.on_exit = on_exit
        self.cwd = cwd

        self._loop: asyncio.AbstractEventLoop | None = None
        self._pid: int | None = None
        self._fd: int | None = None
        self._finished = False

    def start(self) -> None:
        if not self.argv:
            raise OSError(errno.EINVAL, "empty argv")
        if self.cwd is not None and not os.path.isdir(self.cwd):
            raise OSError(errno.ENOENT, f"no such directory: {self.cwd}")

        loop = asyncio.get_running_loop()
        self._loop = loop
        pid, fd = pty.fork()
        if pid == 0:
            try:
                os.environ["TERM"] = "xterm-256color"
                os.environ["COLORTERM"] = "truecolor"
                if self.cwd is not None:
                    os.chdir(self.cwd)
                os.execvp(self.argv[0], self.argv)
            except OSError as e:
                try:
                    message = f"ansiko: cannot start {self.argv[0]!r}: {e.strerror}\r\n"
                    os.write(2, message.encode())
                finally:
                    os._exit(127)

        self._pid = pid
        self._fd = fd
        os.set_blocking(fd, False)
        self.resize(self.cols, self.rows)
        loop.add_reader(fd, self._read_ready)
        threading.Thread(
            target=self._wait_for_exit, name=f"ansiko-wait-{pid}", daemon=True
        ).start()

    def _wait_for_exit(self) -> None:
        assert self._pid is not None
        try:
            _, status = os.waitpid(self._pid, 0)
            code = os.waitstatus_to_exitcode(status)
        except (ChildProcessError, OSError):
            code = -1
        assert self._loop is not None
        self._loop.call_soon_threadsafe(self._finish, code)

    def _read_ready(self) -> None:
        fd = self._fd
        if fd is None:
            return
        while True:
            try:
                data = os.read(fd, 64 * 1024)
            except BlockingIOError:
                return
            except OSError:
                self._stop_reading()
                return
            if not data:
                self._stop_reading()
                return
            self.on_output(data)

    def _stop_reading(self) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        if self._loop is not None:
            self._loop.remove_reader(fd)
        try:
            os.close(fd)
        except OSError:
            pass

    def _finish(self, code: int) -> None:
        if self._finished:
            return
        self._finished = True
        self._stop_reading()
        self.on_exit(code)

    async def write(self, data: bytes) -> None:
        fd = self._fd
        if fd is None:
            return
        view = memoryview(data)
        while view:
            try:
                written = os.write(fd, view)
            except (BlockingIOError, OSError):
                return
            view = view[written:]

    def resize(self, cols: int, rows: int) -> None:
        self.cols, self.rows = cols, rows
        fd = self._fd
        if fd is None:
            return
        try:
            fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

    def refresh(self) -> None:
        """Ask the foreground program to redraw after a display reset.

        TIOCSWINSZ only raises SIGWINCH when the size actually changes, so a
        phone reconnecting at the same grid size would otherwise stay blank.
        """
        fd = self._fd
        if fd is None or self._finished:
            return
        try:
            pgid = os.tcgetpgrp(fd)
        except OSError:
            pgid = self._pid
        if not pgid or pgid <= 0:
            pgid = self._pid
        if pgid is None:
            return
        try:
            os.killpg(pgid, signal.SIGWINCH)
        except (ProcessLookupError, PermissionError):
            pass

    def stop(self) -> None:
        if self._finished:
            return
        self._stop_reading()
        if self._pid is None:
            return
        try:
            os.killpg(self._pid, signal.SIGHUP)
        except ProcessLookupError:
            return
        if self._loop is not None:
            self._loop.call_later(0.5, self._force_terminate)

    def _force_terminate(self) -> None:
        if self._finished or self._pid is None:
            return
        try:
            os.killpg(self._pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
