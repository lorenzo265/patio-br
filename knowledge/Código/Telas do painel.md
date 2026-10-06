---
tipo: "código"
fonte: "nuvem/src/nuvem/web/telas/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/web/telas/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Telas do painel

Os arquivos Jinja de `nuvem/src/nuvem/web/telas/`, a função que mostra cada um e de quem ele herda ou o que inclui. O que cada tela mostra está na [[6.2 Telas do MVP|seção 6.2]] do SDD.

| Tela | Mostrada por | Estende | Inclui |
|---|---|---|---|
| `_alertas_whatsapp.html` |  |  |  |
| `administracao_alertas.html` | `nuvem.web.alertas.tela_da_administracao` | `base.html` | `_alertas_whatsapp.html` |
| `administracao_caixa.html` | `nuvem.web.frota.tela_da_caixa` | `base.html` |  |
| `administracao_demonstracao.html` | `nuvem.web.demonstracao._tela_dos_links` | `base.html` |  |
| `administracao_frota.html` | `nuvem.web.frota.tela_da_frota` | `base.html` |  |
| `administracao_versoes.html` | `nuvem.web.frota._tela_das_versoes` | `base.html` |  |
| `agendamentos.html` | `nuvem.web.agendamentos._tela` | `base.html` |  |
| `agendar.html` | `nuvem.web.agendar._formulario` | `base.html` |  |
| `agendar_aviso.html` | `nuvem.web.agendar._aviso` | `base.html` |  |
| `agendar_feito.html` | `nuvem.web.agendar.feito` | `base.html` |  |
| `alertas.html` | `nuvem.web.alertas.tela_dos_alertas` | `base.html` | `_alertas_whatsapp.html` |
| `alertas_sino.html` | `nuvem.web.alertas.sino`, `nuvem.web.alertas.sino_da_administracao` |  |  |
| `alertas_whatsapp.html` | `nuvem.web.alertas._whatsapp` | `base.html` |  |
| `aviso.html` | `nuvem.principal._csrf_recusado`, `nuvem.principal._nao_encontrado`, `nuvem.principal._sem_permissao`, `nuvem.web.agendamentos._tela`, `nuvem.web.demonstracao._aviso`, `nuvem.web.demonstracao._link_fora`, `nuvem.web.demonstracao.andamento`, `nuvem.web.demonstracao.entrar_pelo_link`, `nuvem.web.extrato._nao_comecou`, `nuvem.web.extrato.extrato_do_mes`, `nuvem.web.extrato.painel`, `nuvem.web.extrato.planilha`, `nuvem.web.mensagens.conversas`, `nuvem.web.patio._mudou`, `nuvem.web.patio.tela_do_patio`, `nuvem.web.portaria.tela_da_portaria` | `base.html` |  |
| `base.html` |  |  |  |
| `demonstracao.html` | `nuvem.web.demonstracao.andamento` | `base.html` |  |
| `demonstracao_link.html` | `nuvem.web.demonstracao.pagina_do_link` | `base.html` |  |
| `entrar.html` | `nuvem.web.rotas.entrar`, `nuvem.web.rotas.tela_de_entrar` | `base.html` |  |
| `entrar_codigo.html` | `nuvem.web.duas_etapas.confirmar_codigo`, `nuvem.web.duas_etapas.tela_do_codigo` | `base.html` |  |
| `entrar_ligar.html` | `nuvem.web.duas_etapas._tela_de_ligar` | `base.html` |  |
| `entrar_recuperacao.html` | `nuvem.web.duas_etapas.ligar` | `base.html` |  |
| `estoque.html` | `nuvem.web.em_breve.estoque` | `base.html` |  |
| `extrato.html` | `nuvem.web.extrato.extrato_do_mes` | `base.html` |  |
| `inicio.html` | `nuvem.web.rotas.inicio` | `base.html` |  |
| `mensagens.html` | `nuvem.web.mensagens.conversas` | `base.html` |  |
| `mensagens_celular.html` | `nuvem.web.mensagens.celular` | `base.html` |  |
| `mensagens_conversa.html` | `nuvem.web.mensagens.conversa` |  |  |
| `mensagens_qr.html` | `nuvem.web.mensagens.qr_da_portaria` | `base.html` |  |
| `painel.html` | `nuvem.web.extrato.painel` | `base.html` |  |
| `patio.html` | `nuvem.web.patio.tela_do_patio` | `base.html` |  |
| `patio_chamar.html` | `nuvem.web.patio._chamar` | `base.html` |  |
| `patio_quadro.html` | `nuvem.web.patio.quadro` |  |  |
| `portaria.html` | `nuvem.web.portaria.tela_da_portaria` | `base.html` |  |
| `portaria_conexao.html` | `nuvem.web.portaria.conexao` |  |  |
| `portaria_conferir.html` | `nuvem.web.portaria._conferir` | `base.html` |  |
| `portaria_excecao.html` | `nuvem.web.resolucao._excecao` | `base.html` |  |
| `portaria_excecoes.html` | `nuvem.web.portaria.lista_de_excecoes` |  |  |
| `portaria_manual.html` | `nuvem.web.resolucao._chegada_manual` | `base.html` |  |
| `portaria_passagens.html` | `nuvem.web.portaria.lista_de_passagens` |  |  |
| `recebimento.html` | `nuvem.web.em_breve.recebimento` | `base.html` |  |
| `trocar_porteiro.html` | `nuvem.web.rotas._tela_da_troca` | `base.html` |  |

---

Do [[Mapa do código]].
