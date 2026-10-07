"""Gerador do escudo dos times: um SVG inline com 3 faixas verticais, uma por
cor do time, recortadas no formato de escudo.

Registrado como global `escudo` do Jinja2 em `web/templates_config.py`:
`{{ escudo(time) }}` ou `{{ escudo(campeao, 96) }}` nos templates.
"""

import itertools
import re

from markupsafe import Markup, escape

import persistencia
from equipe import Equipe

# Escudo cinza para times sem cores conhecidas (ex.: nome fora do catálogo)
# ou com alguma cor inválida.
CORES_ESCUDO_PADRAO = ["#9E9E9E", "#BDBDBD", "#9E9E9E"]

# Contorno do escudo no viewBox 0 0 100 120: topo reto (cantos levemente
# arredondados), laterais retas que curvam até a ponta inferior arredondada.
CONTORNO_ESCUDO = (
    "M8,4 H92 Q96,4 96,8 V56 "
    "C96,84 76,102 52,115 Q50,116 48,115 "
    "C24,102 4,84 4,56 V8 Q4,4 8,4 Z"
)

COR_BORDA = "#1A1A1A"

_PADRAO_HEX = re.compile(r"#[0-9A-Fa-f]{6}")

# Contador de módulo: garante um id de clipPath único por escudo gerado
# (várias SVGs inline na mesma página não podem repetir id).
_contador_ids = itertools.count(1)


def _nome_do_time(time):
    """Devolve o nome do time (Equipe ou string) ou "" quando não há time."""
    if time is None:
        return ""
    if isinstance(time, Equipe):
        return time.nome
    return str(time)


def _cores_validas(cores):
    """True se `cores` tem exatamente 3 hex no formato `#RRGGBB`."""
    if not isinstance(cores, (list, tuple)) or len(cores) != 3:
        return False
    return all(
        isinstance(cor, str) and _PADRAO_HEX.fullmatch(cor) for cor in cores
    )


def _resolver_cores(time):
    """Escolhe as cores do escudo: `Equipe.cores` → catálogo do elenco
    padrão (`persistencia.cores_do_time`) → cinza padrão.
    """
    cores = None
    if isinstance(time, Equipe) and time.cores is not None:
        cores = time.cores
    else:
        nome = _nome_do_time(time)
        if nome:
            cores = persistencia.cores_do_time(nome)

    if cores is None or not _cores_validas(cores):
        return list(CORES_ESCUDO_PADRAO)
    return list(cores)


def escudo_svg(time, tamanho=24):
    """Gera o SVG inline do escudo de `time` (Equipe, string ou None).

    `tamanho` é a largura em pixels; a altura segue a proporção 1:1.2 do
    escudo. Retorna `Markup` para o Jinja2 não escapar o SVG — por isso o
    nome é escapado aqui e as cores são validadas antes de entrar no HTML.
    """
    nome = _nome_do_time(time)
    rotulo = escape(f"Escudo do {nome}" if nome else "Escudo")
    cores = _resolver_cores(time)
    id_clip = f"escudo-clip-{next(_contador_ids)}"
    largura = int(tamanho)
    altura = round(largura * 1.2)

    faixas = "".join(
        f'<rect x="{i * 100 / 3:.2f}" y="0" width="33.34" height="120" '
        f'fill="{cor}"/>'
        for i, cor in enumerate(cores)
    )

    svg = (
        f'<svg class="escudo" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 100 120" width="{largura}" height="{altura}" '
        f'role="img" aria-label="{rotulo}">'
        f"<title>{rotulo}</title>"
        f'<defs><clipPath id="{id_clip}">'
        f'<path d="{CONTORNO_ESCUDO}"/>'
        f"</clipPath></defs>"
        f'<g clip-path="url(#{id_clip})">{faixas}</g>'
        f'<path d="{CONTORNO_ESCUDO}" fill="none" stroke="{COR_BORDA}" '
        f'stroke-width="4" stroke-linejoin="round"/>'
        f"</svg>"
    )
    return Markup(svg)
