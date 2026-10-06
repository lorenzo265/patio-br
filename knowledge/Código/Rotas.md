---
tipo: "código"
fonte: "nuvem/src/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Rotas

Os endereços da API e das telas, lidos dos decoradores (`@roteador.get(...)`) com o prefixo do `APIRouter` de cada módulo.

| Endereço | Método | Função | Pacote | O que faz |
|---|---|---|---|---|
| `/` | GET | `inicio` | [[nuvem.web]] | A tela inicial de quem entrou. |
| `/administracao/demonstracao` | GET | `lista_de_links` | [[nuvem.web]] | Os links de demonstração e o formulário de gerar um novo. |
| `/administracao/demonstracao` | POST | `gerar_link` | [[nuvem.web]] | Gera um link para uma empresa visitada e mostra o endereço, uma vez só. |
| `/administracao/demonstracao/{link_id}/revogar` | POST | `revogar_link` | [[nuvem.web]] | Revoga o link: ele deixa de valer, e as pessoas da empresa dele saem na hora. |
| `/agendamentos` | GET | `tela_de_agendamentos` | [[nuvem.web]] | A lista do dia (ou da semana) de um site do gestor, com a planilha e os links. |
| `/agendamentos/links` | POST | `gerar_link` | [[nuvem.web]] | Gera um link para uma transportadora e mostra o endereço, uma vez só. |
| `/agendamentos/links/{link_id}/revogar` | POST | `revogar_link` | [[nuvem.web]] | Revoga um link: ele deixa de valer na hora. |
| `/agendamentos/modelo.csv` | GET | `baixar_modelo_csv` | [[nuvem.web]] | O modelo da planilha em CSV (só o cabeçalho). |
| `/agendamentos/modelo.xlsx` | GET | `baixar_modelo_xlsx` | [[nuvem.web]] | O modelo da planilha em XLSX (a agenda vazia e uma aba de exemplo). |
| `/agendamentos/planilha` | POST | `subir_planilha` | [[nuvem.web]] | Importa a planilha no site e mostra o relatório por linha. |
| `/agendamentos/{agendamento_id}/cancelar` | POST | `cancelar` | [[nuvem.web]] | Cancela um agendamento e volta à lista do dia dele. |
| `/agendar/{codigo}` | GET | `formulario` | [[nuvem.web]] | O formulário do link, vazio. |
| `/agendar/{codigo}` | POST | `agendar` | [[nuvem.web]] | Cria o agendamento e leva à confirmação; com erro, volta o formulário com os motivos. |
| `/agendar/{codigo}/feito/{numero}` | GET | `feito` | [[nuvem.web]] | A confirmação de um agendamento feito por este link. |
| `/api/admin/caixas` | GET | `listar_caixas` | [[nuvem.frota]] | Todas as caixas, das mais novas para as mais antigas. |
| `/api/admin/caixas/{caixa_id}/revogar` | POST | `revogar` | [[nuvem.frota]] | Revoga a chave da caixa (404 se a caixa não existir). |
| `/api/admin/empresas` | GET | `listar_empresas` | [[nuvem.cadastro]] | Todas as empresas (só a administração). |
| `/api/admin/sites` | GET | `listar_sites_para_administracao` | [[nuvem.cadastro]] | Todos os sites, de todas as empresas (só a administração). |
| `/api/admin/sites/{site_id}/codigos-de-ativacao` | POST | `gerar_codigo` | [[nuvem.frota]] | Gera um código de ativação para o site (vale 24 horas, uma vez). |
| `/api/admin/usuarios/{usuario_id}/duas-etapas/zerar` | POST | `zerar_duas_etapas` | [[nuvem.cadastro]] | Zera a verificação em duas etapas de um usuário e fecha as sessões dele ([[D-60]]). |
| `/api/agendamentos` | GET | `listar` | [[nuvem.agendamento]] | Os agendamentos de um site cuja janela toca o período ``[de, ate)`` (até 31 dias). |
| `/api/agendamentos/planilha` | POST | `subir_planilha` | [[nuvem.agendamento]] | Importa a planilha (CSV ou XLSX) num site do gestor; devolve o relatório por linha. |
| `/api/agendamentos/{agendamento_id}` | GET | `obter` | [[nuvem.agendamento]] | Um agendamento de um site que o usuário vê (404 para qualquer outro). |
| `/api/borda/ativar` | POST | `ativar` | [[nuvem.frota]] | Troca o código de ativação pela chave da caixa (401 se o código não vale). |
| `/api/borda/configuracao` | GET | `configuracao` | [[nuvem.frota]] | As faixas e câmeras do site da caixa, com a senha das câmeras. |
| `/api/borda/fotos/endereco` | POST | `endereco_de_foto` | [[nuvem.portaria]] | Devolve o endereço temporário para a caixa enviar uma foto. |
| `/api/borda/fotos/envio/{codigo}` | PUT | `receber_foto` | [[nuvem.portaria]] | Recebe a foto no armazenamento local (o endereço já autoriza; não leva a chave). |
| `/api/borda/passagens` | POST | `receber_passagem` | [[nuvem.portaria]] | Recebe uma passagem da caixa: 201 se nova, 200 se repetida. |
| `/api/cadastro/sites` | GET | `listar_sites` | [[nuvem.cadastro]] | Os sites que o usuário vê. |
| `/api/cadastro/sites/{site_id}` | GET | `obter_site` | [[nuvem.cadastro]] | Um site que o usuário vê (404 para qualquer outro). |
| `/api/cadastro/sites/{site_id}/cameras` | GET | `listar_cameras` | [[nuvem.cadastro]] | As câmeras de um site que o gestor vê (404 para qualquer outro site). |
| `/api/cron/diaria` | GET | `diaria` | [[nuvem]] | Apaga as empresas de demonstração vencidas e confere o "não veio". |
| `/api/whatsapp` | GET | `conferir_o_webhook` | [[nuvem.mensagens]] | A conferência da Meta: devolve o desafio se o código for o nosso. |
| `/api/whatsapp` | POST | `receber_o_aviso` | [[nuvem.mensagens]] | Guarda o aviso assinado numa tarefa e responde logo (a Meta repete o que demora). |
| `/demonstracao` | GET | `andamento` | [[nuvem.web]] | O dia de demonstração de um site do gestor: o botão de começar ou o andamento. |
| `/demonstracao/comecar` | POST | `comecar` | [[nuvem.web]] | Começa o dia de demonstração do site. |
| `/demonstracao/link/{codigo}` | GET | `pagina_do_link` | [[nuvem.web]] | Para quem é a demonstração e o botão de entrar; não cria nada. |
| `/demonstracao/link/{codigo}` | POST | `entrar_pelo_link` | [[nuvem.web]] | Entra na empresa de demonstração do link como gestor (cria a empresa na primeira vez). |
| `/demonstracao/papel` | POST | `trocar_de_papel` | [[nuvem.web]] | A faixa da demonstração: passa a sessão para a pessoa do papel, na mesma empresa. |
| `/entrar` | GET | `tela_de_entrar` | [[nuvem.web]] | O formulário de e-mail e senha. |
| `/entrar` | POST | `entrar` | [[nuvem.web]] | Confere e-mail e senha; se baterem, abre a sessão e leva ao início. |
| `/entrar/codigo` | GET | `tela_do_codigo` | [[nuvem.web]] | Pede o código do app (ou um código de recuperação). |
| `/entrar/codigo` | POST | `confirmar_codigo` | [[nuvem.web]] | Confere o código; se bater, abre a sessão de sempre e leva ao início. |
| `/entrar/ligar` | GET | `tela_de_ligar` | [[nuvem.web]] | O QR para o app e o segredo em texto, para quem liga a verificação pela primeira vez. |
| `/entrar/ligar` | POST | `ligar` | [[nuvem.web]] | Liga a verificação com o primeiro código do app e mostra os códigos de recuperação. |
| `/estoque` | GET | `estoque` | [[nuvem.web]] | O armazém em 3D, com a busca, e dados de exemplo. |
| `/extrato` | GET | `extrato_do_mes` | [[nuvem.web]] | O extrato em R$ de um mês (o atual, se nenhum for pedido). |
| `/extrato.csv` | GET | `planilha` | [[nuvem.web]] | O extrato de um mês em planilha. |
| `/mensagens` | GET | `conversas` | [[nuvem.web]] | As últimas conversas de um site do usuário (o primeiro, se nenhum for pedido). |
| `/mensagens/agendamentos/{agendamento_id}` | GET | `celular` | [[nuvem.web]] | A tela em forma de celular, com a conversa de um agendamento. |
| `/mensagens/agendamentos/{agendamento_id}/conversa` | GET | `conversa` | [[nuvem.web]] | As mensagens de um agendamento (o pedaço da tela que o HTMX troca), com o dia de cada uma. |
| `/mensagens/qr` | GET | `qr_da_portaria` | [[nuvem.web]] | A placa para imprimir: o QR que abre o WhatsApp com "AVISOS S<site>" ([[D-58]]). |
| `/painel` | GET | `painel` | [[nuvem.web]] | O dia, o mês até agora e cada dia do mês de um site do gestor. |
| `/patio` | GET | `tela_do_patio` | [[nuvem.web]] | O pátio de um site do usuário (o primeiro, se nenhum for pedido). |
| `/patio/quadro` | GET | `quadro` | [[nuvem.web]] | A fila, as docas e os liberados (o pedaço da tela que o HTMX troca). |
| `/patio/visitas/{visita_id}/cancelar-chamada` | POST | `cancelar_chamada` | [[nuvem.web]] | O caminhão chamado não veio: volta para a fila. |
| `/patio/visitas/{visita_id}/chamar` | GET | `tela_de_chamar` | [[nuvem.web]] | As docas livres do site, para chamar o caminhão. |
| `/patio/visitas/{visita_id}/chamar` | POST | `chamar` | [[nuvem.web]] | Chama o caminhão para a doca escolhida. |
| `/patio/visitas/{visita_id}/comecar` | POST | `comecar` | [[nuvem.web]] | O caminhão chegou à doca. |
| `/patio/visitas/{visita_id}/terminar` | POST | `terminar` | [[nuvem.web]] | Terminou a carga ou a descarga. |
| `/portaria` | GET | `tela_da_portaria` | [[nuvem.web]] | A tela da portaria de um site do usuário (o primeiro, se nenhum for pedido). |
| `/portaria/chegada-manual` | GET | `tela_da_chegada_manual` | [[nuvem.web]] | As placas; com elas, os agendamentos sugeridos pelos pontos. |
| `/portaria/chegada-manual` | POST | `registrar_chegada_manual` | [[nuvem.web]] | Registra a chegada com o agendamento escolhido (ou nenhum). |
| `/portaria/conferir/{passagem_id}` | GET | `tela_de_conferir` | [[nuvem.web]] | Os recortes de placa de uma passagem, para o porteiro confirmar ou corrigir ([[D-42]]). |
| `/portaria/conferir/{passagem_id}` | POST | `conferir` | [[nuvem.web]] | Grava a placa certa de um recorte e volta para a página da conferência. |
| `/portaria/excecoes` | GET | `lista_de_excecoes` | [[nuvem.web]] | As exceções abertas do site, da chegada mais antiga para a mais nova (só ver). |
| `/portaria/excecoes/{excecao_id}` | GET | `tela_da_excecao` | [[nuvem.web]] | A exceção, com a foto, as placas, os agendamentos possíveis e as ações. |
| `/portaria/excecoes/{excecao_id}/agendamento` | POST | `e_este` | [[nuvem.web]] | "É este": liga a chegada ao agendamento escolhido. |
| `/portaria/excecoes/{excecao_id}/cavalo` | POST | `digitar_cavalo` | [[nuvem.web]] | A placa do cavalo digitada, quando não há foto; o casamento roda de novo. |
| `/portaria/excecoes/{excecao_id}/conferir` | POST | `corrigir_na_foto` | [[nuvem.web]] | Confere a placa de uma foto da exceção; se ela muda, o casamento roda de novo. |
| `/portaria/excecoes/{excecao_id}/recusar` | POST | `recusar` | [[nuvem.web]] | Recusa a entrada. |
| `/portaria/excecoes/{excecao_id}/sem-agendamento` | POST | `sem_agendamento` | [[nuvem.web]] | Aceita a chegada sem agendamento. |
| `/portaria/fotos/{passagem_id}/{indice}` | GET | `foto` | [[nuvem.web]] | Uma foto de uma passagem que o usuário vê (404 para qualquer outra). |
| `/portaria/passagens` | GET | `lista_de_passagens` | [[nuvem.web]] | A lista das últimas passagens (o pedaço da tela que o HTMX troca). |
| `/recebimento` | GET | `recebimento` | [[nuvem.web]] | A conferência de uma nota na doca, com dados de exemplo. |
| `/sair` | POST | `sair` | [[nuvem.web]] | Fecha a sessão no servidor e apaga o cookie. |
| `/trocar-porteiro` | GET | `tela_de_trocar_porteiro` | [[nuvem.web]] | Os porteiros que podem assumir o tablet, e o campo do PIN. |
| `/trocar-porteiro` | POST | `trocar_porteiro` | [[nuvem.web]] | Passa a sessão para o porteiro escolhido, se o PIN dele conferir. |

---

Do [[Mapa do código]].
