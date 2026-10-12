# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Count and time calls to the secret backends (#71)."""

import time
from collections.abc import Iterator
from contextlib import contextmanager

from hvac.exceptions import Forbidden, InvalidPath

from chronowarden.metrics.prometheus import VAULT_OPERATION_DURATION_SECONDS, VAULT_OPERATIONS_TOTAL


@contextmanager
def observe_vault_operation(operation: str) -> Iterator[None]:
    """
    Time one backend call and count it by outcome: `success`, `not_found`, `forbidden` or `error`.

    Exceptions pass through unchanged; the caller handles them as before.
    """
    start = time.perf_counter()
    status = "error"
    try:
        yield
        status = "success"
    except InvalidPath:
        status = "not_found"
        raise
    except Forbidden:
        status = "forbidden"
        raise
    finally:
        VAULT_OPERATION_DURATION_SECONDS.labels(operation=operation).observe(time.perf_counter() - start)
        VAULT_OPERATIONS_TOTAL.labels(operation=operation, status=status).inc()
