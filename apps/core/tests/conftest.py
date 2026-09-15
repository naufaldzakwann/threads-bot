"""Isolasi test: DB sementara + worker mati. Dibaca pytest sebelum test apa pun jalan."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="thbtest-")
os.environ["THBUZZER_DATA_DIR"] = _tmp
os.environ["THBUZZER_NO_WORKER"] = "1"

from thbuzzer.config import get_settings  # noqa: E402

get_settings.cache_clear()
