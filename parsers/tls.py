"""Дополнительная цепочка доверия только для трёх фирменных источников."""

from functools import lru_cache
from pathlib import Path
import ssl
from urllib.parse import urlsplit


CERTIFICATE_HOSTS = {'job.alfabank.ru', 'www.tbank.ru', 'hr.tochka.com'}
CA_BUNDLE = Path(__file__).with_name('certificates') / 'russian_trusted_ca.pem'


@lru_cache(maxsize=1)
def _context():
    # Системные CA, проверка hostname и CERT_REQUIRED сохраняются.
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=str(CA_BUNDLE))
    return context


def source_ssl_context(url):
    if urlsplit(url).hostname in CERTIFICATE_HOSTS:
        return _context()
    return True
