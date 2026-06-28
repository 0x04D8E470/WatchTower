import structlog
from .config import settings

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(settings.log_level),
    context_class=dict,
    processors=[structlog.processors.add_log_level, structlog.dev.ConsoleRenderer()],
)
logger = structlog.get_logger()