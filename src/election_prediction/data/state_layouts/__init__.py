"""States whose official release format changed between 2024 and 2026.

One module per state, each registering three things:

* ``@register_historical(ST)`` — parser for the 2024-format release, which must reproduce
  the certified 2024 result exactly (``state_extraction.reconcile``);
* ``@register(ST)`` — parser for the 2026-format release, cross-checked race by race
  against the state's own separately published summary (``state_extraction.cross_check``);
* ``@state_fetchers.register(ST)`` — honest-client fetcher for the 2026 release.

Importing this package registers every state module in it.
"""

import importlib
import pkgutil

for _module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_module.name}")
