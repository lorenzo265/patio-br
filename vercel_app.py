"""A entrada da Vercel (D-51 e D-56): a nuvem como uma função, configurada pelo ambiente.

A Vercel carrega o ``app`` daqui (``[tool.vercel] entrypoint`` no ``pyproject.toml``). Os
valores vêm das variáveis de ambiente do projeto na Vercel (``PATIO_*`` e ``CRON_SECRET``); o
passo a passo está em ``docs/guias/demonstracao-na-internet.md``.
"""

from nuvem.principal import criar_app

app = criar_app()
