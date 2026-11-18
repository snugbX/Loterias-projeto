"""Request a Render deployment without printing the secret hook URL."""

import os
import sys
import urllib.request
from urllib.parse import urlsplit


def main():
    hook = os.environ.get('RENDER_DEPLOY_HOOK', '').strip()
    if not hook:
        print('Deploy hook não configurado; nenhum deploy foi solicitado.')
        return 0
    try:
        parsed = urlsplit(hook)
        if parsed.scheme != 'https' or parsed.hostname != 'api.render.com' or parsed.username or parsed.password:
            raise ValueError()
        request = urllib.request.Request(hook, data=b'', method='POST')
        # A hook is a credential: never follow a redirect to another endpoint.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise ValueError()
    except Exception:
        print('Não foi possível solicitar o deploy no Render. Confira o secret e o painel do serviço.', file=sys.stderr)
        return 1
    print('Deploy solicitado ao Render. A conclusão deve ser conferida no painel do serviço.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
