"""Suppress SDK wire/OAuth diagnostics during synchronous private I/O."""
from functools import wraps
import logging


def private_transport(operation):
    @wraps(operation)
    def wrapped(*args, **kwargs):
        # OAuth libraries log redirect codes at INFO and tokens/responses at DEBUG.
        # This single-user synchronous CLI has no background logging workers.
        previous = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return operation(*args, **kwargs)
        finally:
            logging.disable(previous)
    return wrapped
