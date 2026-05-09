from pathlib import Path
import tempfile

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if config.option.basetemp is None:
        config.option.basetemp = str(Path(tempfile.gettempdir()) / "predictpay_pytest_tmp")
