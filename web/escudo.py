"""Gerador do escudo dos times: um SVG inline em formato quadrado com
cantos arredondados (a largura é igual à altura) e borda branca fina.

As 1 a 4 cores do time são desenhadas conforme o padrão do escudo (um de
`catalogo.PADROES`):
- verticais: faixas de mesma largura, da esquerda para a direita;
- horizontais: faixas de mesma altura, de cima para baixo;
- diagonal_sobe (↗) / diagonal_desce (↘): a cor 1 é o fundo e as demais
  formam uma faixa inclinada de `LARGURA_DIAGONAL`, lado a lado dentro dela.

Registrado como global `escudo` do Jinja2 em `web/templates_config.py`:
`{{ escudo(time) }}`, `{{ escudo(campeao, 96) }}` ou, na prévia do adm,
`{{ escudo(id_time, 96, cores=[...], padrao=...) }}`. `time` pode ser uma
`Equipe`, o id do time (`int`, formato do histórico), uma string crua (só
texto: escudo cinza) ou None.
"""

import itertools

from markupsafe import Markup, escape

import catalogo
from equipe import Equipe

# Escudo cinza para times sem cores conhecidas (ex.: id fora do catálogo)
# ou com alguma cor inválida. É sempre desenhado com faixas verticais.
CORES_ESCUDO_PADRAO = ["#9E9E9E", "#BDBDBD"]

# Geometria no viewBox quadrado 0 0 60 60 (largura = altura): faixas com
# largura/altura inteira para 1 a 4 cores (60/30/20/15).
LARGURA_VIEWBOX = 60
ALTURA_VIEWBOX = 60
RAIO_CANTO = 8
CENTRO_VIEWBOX = LARGURA_VIEWBOX / 2

# Espessura total da faixa diagonal em unidades do viewBox (40% do lado:
# ~8 px no escudo de 20 px). As faixas são compridas de sobra (o clipPath
# corta o excesso) para cobrir o quadrado inteiro depois de giradas.
LARGURA_DIAGONAL = 24
COMPRIMENTO_DIAGONAL = 2 * LARGURA_VIEWBOX

# Ângulo do `rotate` de cada sentido da diagonal: ↗ gira -45° (sobe da
# esquerda para a direita), ↘ gira 45°.
ANGULOS_DIAGONAL = {
    catalogo.PADRAO_DIAGONAL_SOBE: -45,
    catalogo.PADRAO_DIAGONAL_DESCE: 45,
}

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
    `Equipe.cores` válidas → None (o chamador usa o cinza padrão). String
    crua não é buscada no catálogo (time é identificado só pelo id).

    Um id conhecido com cores inválidas no catálogo também devolve None (não
    cai para as cores da `Equipe`, que são só um retrato salvo).
    """
    id_time = _id_do_time(time)
    if id_time is not None:
        cores = catalogo.cores_do_time(id_time)
        if cores is not None:
            return list(cores) if catalogo.cores_validas(cores) else None

    if isinstance(time, Equipe) and catalogo.cores_validas(time.cores):
        return list(time.cores)

    return None


def _resolver_padrao(time, padrao, cores):
    """Escolhe o padrão do escudo: `padrao` explícito (prévia do adm) →
    padrão do id no catálogo → verticais. Se o escolhido não combina com
    as cores (`catalogo.padrao_valido`: valor desconhecido, diagonal com
    menos de 2 cores), cai para verticais.
    """
    if padrao is None:
        id_time = _id_do_time(time)
        if id_time is not None:
            padrao = catalogo.padrao_do_time(id_time)
    if catalogo.padrao_valido(padrao, cores):
        return padrao
    return catalogo.PADRAO_VERTICAIS


def _numero(valor):
    """Formata um número para atributo SVG sem zeros inúteis (12, 12.5)."""
    return f"{valor:.4f}".rstrip("0").rstrip(".")


def _faixas_verticais(cores):
    """N faixas de mesma largura, da esquerda para a direita."""
    largura_faixa = LARGURA_VIEWBOX / len(cores)
    return "".join(
        f'<rect x="{_numero(i * largura_faixa)}" y="0" '
        f'width="{_numero(largura_faixa)}" height="{ALTURA_VIEWBOX}" '
        f'fill="{cor}"/>'
        for i, cor in enumerate(cores)
    )


def _faixas_horizontais(cores):
    """N faixas de mesma altura, de cima para baixo."""
    altura_faixa = ALTURA_VIEWBOX / len(cores)
    return "".join(
        f'<rect x="0" y="{_numero(i * altura_faixa)}" '
        f'width="{LARGURA_VIEWBOX}" height="{_numero(altura_faixa)}" '
        f'fill="{cor}"/>'
        for i, cor in enumerate(cores)
    )


def _faixas_diagonal(cores, angulo):
    """Fundo na cor 1 + faixa inclinada com as cores 2..N lado a lado.

    As faixas são desenhadas na horizontal, centradas no meio do quadrado,
    e o grupo é girado `angulo` graus em torno do centro. A cor 2 fica do
    lado de cima/esquerda da faixa.
    """
    fundo, *cores_faixa = cores
    espessura = LARGURA_DIAGONAL / len(cores_faixa)
    inicio_y = CENTRO_VIEWBOX - LARGURA_DIAGONAL / 2
    inicio_x = CENTRO_VIEWBOX - COMPRIMENTO_DIAGONAL / 2
    centro = _numero(CENTRO_VIEWBOX)
    faixas = "".join(
        f'<rect x="{_numero(inicio_x)}" '
        f'y="{_numero(inicio_y + i * espessura)}" '
        f'width="{_numero(COMPRIMENTO_DIAGONAL)}" '
        f'height="{_numero(espessura)}" fill="{cor}"/>'
        for i, cor in enumerate(cores_faixa)
    )
    return (
        f'<rect x="0" y="0" width="{LARGURA_VIEWBOX}" '
        f'height="{ALTURA_VIEWBOX}" fill="{fundo}"/>'
        f'<g class="escudo-diagonal" '
        f'transform="rotate({angulo} {centro} {centro})">{faixas}</g>'
    )


def _desenhar_faixas(padrao, cores):
    """SVG interno do grupo recortado para o `padrao` (já validado)."""
    if padrao == catalogo.PADRAO_HORIZONTAIS:
        return _faixas_horizontais(cores)
    if padrao in ANGULOS_DIAGONAL:
        return _faixas_diagonal(cores, ANGULOS_DIAGONAL[padrao])
    return _faixas_verticais(cores)


def escudo_svg(time, tamanho=24, cores=None, padrao=None):
    """Gera o SVG inline do escudo de `time` (Equipe, id, string ou None).

    `tamanho` é a ALTURA em pixels; o escudo é quadrado, então a largura é
    igual à altura. `cores` e `padrao`, se informados, substituem os do
    time (prévia do adm). Cores inválidas viram o escudo cinza, que é
    sempre vertical; padrão desconhecido ou que não combina com as cores
    (diagonal com 1 cor) vira verticais. Retorna `Markup` para o Jinja2 não
    escapar o SVG — por isso o nome é escapado aqui e as cores são
    validadas antes de entrar no HTML.
    """
    nome = catalogo.nome_para_exibir(time)
    rotulo = escape(f"Escudo do {nome}" if nome else "Escudo")
    if cores is not None:
        cores = list(cores) if catalogo.cores_validas(cores) else None
    else:
        cores = _resolver_cores(time)
    if cores is None:
        cores = list(CORES_ESCUDO_PADRAO)
        padrao = catalogo.PADRAO_VERTICAIS
    else:
        padrao = _resolver_padrao(time, padrao, cores)
    id_clip = f"escudo-clip-{next(_contador_ids)}"
    altura = int(tamanho)
    largura = _numero(altura * LARGURA_VIEWBOX / ALTURA_VIEWBOX)

    faixas = _desenhar_faixas(padrao, cores)

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
