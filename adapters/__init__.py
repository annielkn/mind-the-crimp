import importlib
import pkgutil

from . import lcc_wordpress, manual, mileend_html

PUBLIC_ADAPTERS = {
    "manual": manual.fetch,
    "lcc_wordpress": lcc_wordpress.fetch,
    "mileend_html": mileend_html.fetch,
}
ADAPTERS = dict(PUBLIC_ADAPTERS)

# Private adapters live in adapters/private/ (gitignored). Each module there that defines
# SOURCE and fetch() is registered under that source name; none of them is required.
PRIVATE = []
try:
    from . import private as _private
except ImportError:
    _private = None
if _private:
    for _info in pkgutil.iter_modules(_private.__path__):
        _mod = importlib.import_module(f"{__name__}.private.{_info.name}")
        if hasattr(_mod, "SOURCE") and hasattr(_mod, "fetch"):
            ADAPTERS[_mod.SOURCE] = _mod.fetch
            PRIVATE.append(_mod)
