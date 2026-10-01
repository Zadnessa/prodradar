"""Проверка цепочек фирменных HTTPS-источников; запускается в Actions."""

import argparse
import json
from pathlib import Path
import re
import ssl
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parsers.tls import CA_BUNDLE, CERTIFICATE_HOSTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # В Actions соединения идут напрямую. В облачной среде требуется proxy;
    # этот диагностический TLS-инструмент там не используется.
    combined = args.output.with_suffix('.ca.pem')
    combined.write_bytes(Path(ssl.get_default_verify_paths().cafile).read_bytes() + CA_BUNDLE.read_bytes())
    results = {}
    try:
        for host in sorted(CERTIFICATE_HOSTS):
            checks = {}
            for name, extra in [('system', []), ('source_chain', ['-CAfile', str(combined)])]:
                try:
                    result = subprocess.run(['openssl', 's_client', '-connect', host + ':443',
                                             '-servername', host, '-verify_hostname', host,
                                             '-verify_return_error', '-showcerts', *extra],
                                            input='', capture_output=True, text=True, timeout=20)
                    checks[name] = {'verified': result.returncode == 0,
                                    'returncode': result.returncode,
                                    'certificate_summary': re.findall(r'(?:subject|issuer)=[^\n]+', result.stdout),
                                    'verification_errors': re.findall(r'verify error:[^\n]+', result.stderr)}
                except subprocess.TimeoutExpired:
                    checks[name] = {'verified': False, 'timeout': True}
            results[host] = checks
            print(json.dumps({'host': host, **checks}), flush=True)
    finally:
        combined.unlink(missing_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
