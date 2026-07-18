"""CPU/RAM/GPU sampling thread active while a run executes."""
import logging
import threading

from app import models

logger = logging.getLogger(__name__)


def _gpu_stats():
    try:
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        pynvml.nvmlShutdown()
        return float(util.gpu), float(mem.used) / (1024**2)
    except Exception:
        return None, None


class ResourceSampler:
    def __init__(self, session_factory, project_id: str, run_id: str, interval: float = 2.0):
        self.session_factory = session_factory
        self.project_id = project_id
        self.run_id = run_id
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        import psutil

        while not self._stop.is_set():
            try:
                gpu_util, gpu_mem = _gpu_stats()
                with self.session_factory() as s:
                    s.add(
                        models.ResourceSample(
                            project_id=self.project_id, run_id=self.run_id,
                            cpu_percent=psutil.cpu_percent(interval=None),
                            mem_percent=psutil.virtual_memory().percent,
                            gpu_util=gpu_util, gpu_mem=gpu_mem,
                        )
                    )
                    s.commit()
            except Exception as exc:
                logger.debug("resource sample failed: %s", exc)
            self._stop.wait(self.interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc_info):
        self._stop.set()
        self._thread.join(timeout=3)
        return False
