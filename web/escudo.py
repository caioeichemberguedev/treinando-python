"""Gerador do escudo dos times: um SVG inline em formato de retângulo com
cantos arredondados (altura = 1,5 × largura), com 1 a 4 faixas verticais de
mesma largura, uma por cor do time, da esquerda para a direita.

Registrado como global `escudo` do Jinja2 em `web/templates_config.py`:
`{{ escudo(time) }}`, `{{ escudo(campeao, 96) }}` ou, na prévia do adm,
`{{ escudo(id_time, 96, cores=[...]) }}`. `time` pode ser uma `Equipe`, o id
do time (`int`, formato do histórico), uma string crua (só texto: escudo
cinza) ou None.
"""

import itertools

from markupsafe import Markup, escape

import catalogo
from equipe import Equipe

# Escudo cinza para times sem cores conhecidas (ex.: id fora do catálogo)
# ou com alguma cor inválida.
CORES_ESCUDO_PADRAO = ["#9E9E9E", "#BDBDBD"]

# Geometria no viewBox 0 0 60 90 (proporção largura:altura = 1:1,5).
LARGURA_VIEWBOX = 60
ALTURA_VIEWBOX = 90
RAIO_CANTO = 8

# Borda em PIXELS DE TELA (não em unidades do viewBox): com
# vector-effect="non-scaling-stroke" o traço fica com 1 px em qualquer tamanho.
ESPESSURA_BORDA = 1
COR_BORDA = "#FFFFFF"

# Contador de módulo: garante um id de clipPath único por escudo gerado
# (várias SVGs inline na mesma página não podem repetir id).
_contador_ids = itertools.count(1)


def _id_do_time(time):
    """Devolve o id do time (de uma `Equipe` ou de um `int`), ou None."""
    if isinstance(time, Equipe):
        return time.id
    if isinstance(time, int) and not isinstance(time, bool):
        return time
    return None


def _resolver_cores(time):
    """Escolhe as cores do escudo, nesta ordem: id conhecido no catálogo →
    `Equipe.cores` válidas → cinza padrão. String crua não é buscada no
    catálogo (time é identificado só pelo id): vira escudo cinza.

    Um id conhecido com cores inválidas no catálogo também vira cinza (não
    cai para as cores da `Equipe`, que são só um retrato salvo).
    """
    id_time = _id_do_time(time)
    if id_time is not None:
        cores = catalogo.cores_do_time(id_time)
        if cores is not None:
            if catalogo.cores_validas(cores):
                return list(cores)
            return list(CORES_ESCUDO_PADRAO)

    if isinstance(time, Equipe) and catalogo.cores_validas(time.cores):
        return list(time.cores)

    return list(CORES_ESCUDO_PADRAO)


def _numero(valor):
    """Formata um número para atributo SVG sem zeros inúteis (12, 12.5)."""
    return f"{valor:.4f}".rstrip("0").rstrip(".")


def escudo_svg(time, tamanho=24, cores=None):
    """Gera o SVG inline do escudo de `time` (Equipe, id, string ou None).

    `tamanho` é a ALTURA em pixels; a largura é 2/3 da altura. `cores`, se
    informado, substitui as cores do time (prévia do adm); cores inválidas
    viram o escudo cinza. Retorna `Markup` para o Jinja2 não escapar o SVG
    — por isso o nome é escapado aqui e as cores são validadas antes de
    entrar no HTML.
    """
    nome = catalogo.nome_para_exibir(time)
    rotulo = escape(f"Escudo do {nome}" if nome else "Escudo")
    if cores is not None:
        cores = (
            list(cores) if catalogo.cores_validas(cores)
            else list(CORES_ESCUDO_PADRAO)
        )
    else:
        cores = _resolver_cores(time)
    id_clip = f"escudo-clip-{next(_contador_ids)}"
    altura = int(tamanho)
    largura = _numero(altura * LARGURA_VIEWBOX / ALTURA_VIEWBOX)

    largura_faixa = LARGURA_VIEWBOX / len(cores)
    faixas = "".join(
        f'<rect x="{_numero(i * largura_faixa)}" y="0" '
        f'width="{_numero(largura_faixa)}" height="{ALTURA_VIEWBOX}" '
        f'fill="{cor}"/>'
        for i, cor in enumerate(cores)
    )

    # Borda recuada meia espessura para o traço não ser cortado nas bordas.
    # A espessura está em px de tela; convertida para unidades do viewBox
    # pela altura (max evita divisão por zero com tamanho <= 0).
    recuo = (ESPESSURA_BORDA / 2) * ALTURA_VIEWBOX / max(altura, 1)
    svg = (
        f'<svg class="escudo" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {LARGURA_VIEWBOX} {ALTURA_VIEWBOX}" '
        f'width="{largura}" height="{altura}" '
        f'role="img" aria-label="{rotulo}">'
        f"<title>{rotulo}</title>"
        f'<defs><clipPath id="{id_clip}">'
        f'<rect x="0" y="0" width="{LARGURA_VIEWBOX}" '
        f'height="{ALTURA_VIEWBOX}" rx="{RAIO_CANTO}" ry="{RAIO_CANTO}"/>'
        f"</clipPath></defs>"
        f'<g class="escudo-faixas" clip-path="url(#{id_clip})">{faixas}</g>'
        f'<rect class="escudo-borda" x="{_numero(recuo)}" '
        f'y="{_numero(recuo)}" '
        f'width="{_numero(LARGURA_VIEWBOX - 2 * recuo)}" '
        f'height="{_numero(ALTURA_VIEWBOX - 2 * recuo)}" '
        f'rx="{_numero(RAIO_CANTO - recuo)}" fill="none" '
        f'stroke="{COR_BORDA}" stroke-width="{ESPESSURA_BORDA}" '
        f'vector-effect="non-scaling-stroke"/>'
        f"</svg>"
    )
    return Markup(svg)
