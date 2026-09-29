###############################################################################
# gunicorn config — production
###############################################################################
import os

# Binding
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5010")

# Workers — per-cpu plus 1, reasonable cap
from multiprocessing import cpu_count
        workers = (cpu_count() * 2) + 1
        workers = min(workers, 16)  # don't overheat
        workers = max(workers, 2)

# Timeout
timeout = 120           # AI image extraction can take time
graceful_timeout = 60

# Logging
accesslog  = "-"        # stdout (Docker)
errorlog   = "-"        # stderr (Docker)
loglevel   = "info"
