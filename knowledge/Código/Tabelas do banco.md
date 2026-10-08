---
tipo: "código"
fonte: "nuvem/src/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Tabelas do banco

As tabelas do PostgreSQL, lidas dos modelos do SQLAlchemy (`__tablename__`), com as colunas na ordem do modelo. As garantias da separação por empresa estão na [[5.5 Garantias|seção 5.5]] do SDD.

| Tabela | Classe | Pacote | Colunas | O que guarda |
|---|---|---|---|---|
| `administrador` | `Administrador` | [[nuvem.cadastro]] | id, nome, email, senha_resumo, ativo | Uma pessoa da administração da plataforma (nós), fora de qualquer empresa ([[D-19]]). |
| `agendamento` | `Agendamento` | [[nuvem.agendamento]] | id, empresa_id, site_id, janela_inicio, janela_fim, tipo, placa_cavalo, placas_reboques, motorista_nome, motorista_celular, toneladas, chave_nfe, origem, codigo_externo, situacao, link_id, criado_em, atualizado_em | Um caminhão esperado no site, numa janela de horário. |
| `agendamento_mudanca` | `MudancaAgendamento` | [[nuvem.agendamento]] | id, empresa_id, agendamento_id, momento, tipo, via, usuario_id, antes, depois | Uma mudança num agendamento: a criação, cada alteração e o cancelamento. |
| `atualizacao_caixa` | `AtualizacaoCaixa` | [[nuvem.frota]] | id, empresa_id, caixa_id, de, versao_id, comecou_em, terminou_em, resultado, motivo, recebida_em | Uma troca de versão, como a caixa contou ([[D-67]]). Só se acrescenta. |
| `autorizacao_whatsapp` | `AutorizacaoWhatsApp` | [[nuvem.mensagens]] | id, empresa_id, celular, autorizada_em, texto, id_no_whatsapp, revogada_em | O celular que autorizou receber os avisos de uma empresa pelo WhatsApp ([[D-58]]). |
| `caixa_borda` | `CaixaBorda` | [[nuvem.frota]] | id, empresa_id, site_id, chave_resumo, ativada_em, revogada_em, ultimo_contato, versao_programa, versao_leitor, ultima_saude, diferenca_do_relogio | Uma caixa de borda (mini PC na portaria) ativada num site. |
| `camera` | `Camera` | [[nuvem.cadastro]] | id, empresa_id, faixa_id, nome, posicao, endereco, login, senha_cifrada | Uma câmera IP da faixa. A senha fica cifrada (ver ``nuvem.cifra``). |
| `codigo_ativacao` | `CodigoAtivacao` | [[nuvem.frota]] | id, empresa_id, site_id, codigo_resumo, criado_por, criado_em, expira_em, usado_em | Um código de uso único que a administração gera para ativar uma caixa num site. |
| `codigo_recuperacao` | `CodigoRecuperacao` | [[nuvem.cadastro]] | id, usuario_id, empresa_id, administrador_id, resumo, usado_em | Um código de recuperação da verificação em duas etapas ([[D-60]]): vale uma vez. |
| `conferencia_placa` | `ConferenciaPlaca` | [[nuvem.portaria]] | id, empresa_id, passagem_id, foto, placa_lida, placa, usuario_id, momento | A placa certa de um recorte, segundo quem conferiu ([[D-42]]). Só se acrescenta ([[5.5 Garantias\|SDD 5.5]]). |
| `dia_de_demonstracao` | `DiaDeDemonstracao` | [[nuvem.demonstracao]] | id, empresa_id, site_id, caixa_id, lider_id, comecou_em, termina_em, chegadas, enviadas, saidas, ultima_acao_em, situacao | Um "começar o dia" de um site de demonstração. |
| `doca` | `Doca` | [[nuvem.cadastro]] | id, empresa_id, site_id, nome | Uma doca de carga e descarga do site. |
| `empresa` | `Empresa` | [[nuvem.cadastro]] | id, nome, cnpj | Um cliente. |
| `escolha_de_versao` | `EscolhaDeVersao` | [[nuvem.frota]] | id, versao_id, empresa_id, site_id, caixa_id, escolhida_em, escolhida_por | A versão escolhida para todas as caixas, para um site ou para uma caixa ([[D-67]]). |
| `evento` | `Evento` | [[nuvem.portaria]] | id, empresa_id, visita_id, tipo, estado, momento, registrado_em, usuario_id, passagem_id, dados | Algo que aconteceu com uma visita. Só se acrescenta ([[5.5 Garantias\|SDD 5.5]]). |
| `excecao` | `Excecao` | [[nuvem.portaria]] | id, empresa_id, visita_id, passagem_id, motivo, candidatos, situacao, criada_em, resolvida_em, resolvida_por, resolucao | Uma chegada que o sistema não casou com segurança: o porteiro resolve ([[5.2 Estados da visita\|SDD 5.2]]). |
| `extrato` | `Extrato` | [[nuvem.extrato]] | id, empresa_id, site_id, mes, versao_da_regra, numeros, guardado_em | O extrato de um mês fechado, como foi calculado na primeira vez. Só se acrescenta. |
| `faixa` | `Faixa` | [[nuvem.cadastro]] | id, empresa_id, portaria_id, nome, sentido | Uma faixa da portaria, de entrada ou de saída. |
| `linha_de_base` | `LinhaDeBase` | [[nuvem.extrato]] | id, empresa_id, site_id, origem, de, ate, medidas, gravada_em | As medidas do site antes do sistema, para comparar cada mês ([[5.4 Contas do extrato\|SDD 5.4]]). |
| `link_demonstracao` | `LinkDemonstracao` | [[nuvem.demonstracao]] | id, nome, codigo_resumo, criado_por, criado_em, vence_em, revogado_em, empresa_id, ultima_entrada_em, apagada_em | Um link de demonstração para uma empresa visitada ([[D-52]] e [[D-54]]). |
| `link_transportadora` | `LinkTransportadora` | [[nuvem.agendamento]] | id, empresa_id, site_id, nome, codigo_resumo, criado_por, criado_em, vence_em, revogado_em, limite_de_envios, envios | Um link de agendamento que o gestor manda a uma transportadora ([[8.2 Segurança\|SDD 8.2]] e [[D-34]]). |
| `mensagem` | `Mensagem` | [[nuvem.mensagens]] | id, empresa_id, site_id, agendamento_id, evento_id, modelo, canal, para, texto, variaveis, situacao, criada_em, id_no_canal, enviada_em, entregue_em, lida_em, falhou_em, erro, cobranca | Uma mensagem ao motorista de um agendamento. |
| `mensagem_recebida` | `MensagemRecebida` | [[nuvem.mensagens]] | id, id_no_whatsapp, de, texto, recebida_em, empresa_id, resultado, tratada_em | Uma mensagem que alguém mandou ao número do produto ([[D-63]]). |
| `parametros_site` | `ParametrosSite` | [[nuvem.extrato]] | id, empresa_id, site_id, valor_da_estadia, franquia_minutos, postos_antes, postos_depois, custo_mensal_do_posto, custo_hora_doca, atualizado_em | Os números do site para o extrato; sem linha aqui, valem os da lei e nada da portaria. |
| `passagem` | `PassagemRecebida` | [[nuvem.portaria]] | id, empresa_id, site_id, caixa_id, faixa_id, sentido, inicio, fim, recebida_em, como_veio | Uma passagem que uma caixa de borda mandou. |
| `portaria` | `Portaria` | [[nuvem.cadastro]] | id, empresa_id, site_id, nome | Uma portaria do site; tem uma ou mais faixas. |
| `saude_caixa` | `SaudeCaixa` | [[nuvem.frota]] | id, empresa_id, caixa_id, recebida_em, momento, diferenca_do_relogio, cpu, temperatura, memoria, disco, cameras_no_ar, cameras, passagens_na_fila, dados | Uma saúde recebida de uma caixa: o histórico curto, de 7 dias ([[D-65]]). |
| `sessao_login` | `SessaoLogin` | [[nuvem.cadastro]] | id, codigo_resumo, usuario_id, empresa_id, administrador_id, criada_em, expira_em, falta | Uma sessão aberta no painel ([[D-20]]): de um usuário do cliente ou da administração. |
| `site` | `Site` | [[nuvem.cadastro]] | id, empresa_id, nome, fuso, abre, fecha | Um local do cliente com portaria e pátio (ex.: um centro de distribuição). |
| `tarefa_de_fundo` | `TarefaDeFundo` | [[nuvem]] | id, tipo, chave, dados, situacao, tentativas, criada_em, executar_em, terminada_em, ultimo_erro | Uma tarefa para o worker. É da plataforma, não de um cliente: os dados dizem o que fazer. |
| `tentativa_login` | `TentativaLogin` | [[nuvem.cadastro]] | id, alvo_resumo, momento | Um erro de senha ou de PIN, para o limite de tentativas ([[8.2 Segurança\|SDD 8.2]]). |
| `usuario` | `Usuario` | [[nuvem.cadastro]] | id, empresa_id, nome, email, papel, senha_resumo, pin_resumo, ativo, duas_etapas_zerada_em, duas_etapas_zerada_por | Uma pessoa do cliente que usa o painel. |
| `usuario_site` | `UsuarioSite` | [[nuvem.cadastro]] | usuario_id, site_id, empresa_id | Os sites que um usuário vê; sempre da mesma empresa do usuário. |
| `versao_caixa` | `VersaoCaixa` | [[nuvem.frota]] | id, nome, imagem, resumo, cadastrada_em, cadastrada_por | Uma versão do agente da caixa, pela imagem e pelo resumo dela ([[D-67]]). |
| `visita` | `Visita` | [[nuvem.portaria]] | id, empresa_id, site_id, agendamento_id, estado, composicao, chegou_em, saiu_em, passagem_entrada_id, passagem_saida_id, criada_em, doca_id, chamada_em, na_doca_em, liberada_em | A estadia de um caminhão no site, da chegada à saída (ou o "não veio"). |

---

Do [[Mapa do código]].
