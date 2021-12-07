"""kytos/ping."""

from threading import Thread, Event
from queue import Queue
from uuid import uuid4
from time import time
import os
from pathlib import Path

from kytos.core import KytosEvent, KytosNApp, log
from kytos.core.helpers import listen_to


class Main(KytosNApp):
    """Main class to be used by Kytos controller."""

    def setup(self):
        """Replace the 'init' method for the KytosApp subclass.

        The setup method is automatically called by the run method.
        Users shouldn't call this method directly.
        """
        log.info("ping starting")
        self.replies = {}
        self.result_queue = Queue()
        self.thread_consumer = Thread(target=self._update_reply)
        self.thread_ev = Event()
        self.thread_consumer.daemon = True
        self.thread_consumer.start()
        self.execute_as_loop(1)

    def publish_ping(self):
        """Publish ping."""
        event_name = "kytos/ping.request"
        content = {"to": "pong", "value": 1}
        event = KytosEvent(name=event_name, content=content)
        self.controller.buffers.app.put(event)

    def publish_ping_many(self, n, event_name="kytos/ping.request"):
        """Publish ping."""
        event_name = event_name
        for i in range(n):
            content = {
                "to": "pong",
                "value": i,
                "id": str(uuid4()),
                "time": time(),
            }
            event = KytosEvent(name=event_name, content=content)
            self.controller.buffers.app.put(event)

    def _write_replies_to_file(
        self, output_file=os.environ.get("PING_OUTPUT_FILE", None)
    ):
        """Write replies to file."""
        if not output_file:
            return
        first_line = "id,value,time_diff\n"
        with open(Path(__file__).parent / output_file, "w") as f:
            f.write(first_line)
            for content in self.replies.values():
                f.write(f"{content['id']},{content['value']},{content['time_diff']}\n")

    def _update_reply(
        self,
        max_records_to_write=int(os.environ.get("PING_MAX_RECORDS_TO_WRITE", 20000)),
    ) -> None:
        """Update reply."""
        while not self.thread_ev.is_set():
            ev = self.result_queue.get()
            log.debug(f"got ev {ev.content}")
            self.replies[ev.content["id"]] = ev.content
            if len(self.replies) >= max_records_to_write:
                self._write_replies_to_file()
                self.thread_ev.set()

    @listen_to("kytos/pong.reply")
    def on_pong(self, event):
        """On pong."""
        log.debug(f"on_pong sub {event.content}")
        t = time()
        event.content["time_reply"] = t
        event.content["time_diff"] = t - event.content["time"]
        self.result_queue.put(event)

    def execute(self):
        """Run once on NApp 'start' or in a loop.

        The execute method is called by the run method of KytosNApp class.
        Users shouldn't call this method directly.
        """
        self.publish_ping_many(5000, "kytos/ping.request")

    def shutdown(self):
        """Shutdown routine of the NApp."""
        log.debug("ping stopping")
        self.thread_ev.set()
