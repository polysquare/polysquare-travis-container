# /psqtraviscontainer/output.py
#
# Helper classes to monitor and capture output as it runs.
#
# See /LICENCE.md for Copyright information
"""Helper classes to monitor and capture output as it runs."""

import sys

import threading


def monitor(stream,
            modifier=None,
            live=False,
            output=sys.stdout):
    """Monitor and print lines from stream until end of file is reached.

    Each line is piped through :modifier:.
    """
    from six import StringIO
    captured = StringIO()
    modifier = modifier or (lambda l: l)

    def read_thread():
        """Read each line from the stream and print it."""
        # No stream, not much we can really do here.
        if not stream:
            return

        for line in stream:
            line = modifier(line)
            captured.write(line)
            if live:
                output.write(line)
                output.flush()

    def joiner_for_output(thread):
        """Closure to join the thread and do something with its output."""
        thread.start()

        def join():
            """Join the thread and then return its output."""
            thread.join()
            captured.seek(0)
            return captured

        return join

    # Note that while it is necessary to call joiner_for_output if you want
    # resources to be cleaned up, it is not necessary if you don't care
    # about cleanup and just want the program to keep running.
    return joiner_for_output(threading.Thread(target=read_thread))
