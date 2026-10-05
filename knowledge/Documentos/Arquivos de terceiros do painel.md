---
tipo: "documento"
fonte: "nuvem/src/nuvem/web/estatico/LEIA-ME.md"
gerada: true
tags: [documento]
---

> [!note] Gerada de `nuvem/src/nuvem/web/estatico/LEIA-ME.md` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Arquivos de terceiros servidos pelo painel

| Arquivo | O que é | Versão | Licença | Origem |
|---|---|---|---|---|
| `htmx-2.0.11.min.js` | [HTMX](https://htmx.org), atualização das telas sem recarregar ([[6.1 Stack\|SDD 6.1]]) | 2.0.11 | Zero-Clause BSD (`htmx-LICENSE.txt`) | pacote `htmx.org` do npm, `dist/htmx.min.js`; conferido pelo sha512 publicado no npm |
| `three-0.186.1/` | [three.js](https://threejs.org), o desenho em 3D do armazém na tela do estoque ("em breve", [[D-43]]) | 0.186.1 | MIT (`three-0.186.1/LICENSE.txt`) | pacote `three` do npm: `build/three.module.js`, `build/three.core.js` e `examples/jsm/controls/OrbitControls.js` (em `addons/controls/`), sem mudança; o pacote conferido pelo sha512 publicado no npm |

SHA-256 de cada arquivo:

- `htmx-2.0.11.min.js`: `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717`
- `three-0.186.1/three.module.js`: `9052042d676cb0fdc1ddfefe193053f34b7ac0513a616fdac4535d49987812ea`
- `three-0.186.1/three.core.js`: `9edde002b066a9a05676a6127f67735b62baf399bdea529f2f7e31657da769e6`
- `three-0.186.1/addons/controls/OrbitControls.js`: `3d79d07ecb686b4e5d93232eedab255331c1beef711e13164eaa1f68655a5f2b`

O pacote do three.js não traz arquivos minificados; vão como vieram (cerca de 2,1 MB, 420 KB
com gzip), para o hash conferir com o do pacote. Um teste confere cada hash desta página.

Ficam no repositório, e não num CDN, para o tablet da portaria não depender de outro servidor.
Para trocar de versão, baixe o pacote do npm, confira o hash e a licença, troque o nome do
arquivo (a versão faz parte do nome) e atualize esta tabela.
