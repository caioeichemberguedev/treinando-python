"""Rotas de edição do elenco base: listar campeonatos, editar
finanças/fãs/força e restaurar os valores padrão.

O elenco de cada campeonato é fixo (ID-004): não há rotas para adicionar,
renomear ou remover equipes — um POST direto nesses caminhos cai em 404/405
sem tocar no `equipes.json`.

Espelha `menu.editar_equipes` e a opção "Restaurar equipes para os valores
padrão" de `menu.menu_principal`. Restaurar o padrão é uma ação destrutiva,
então passa por uma tela de confirmação antes do POST que efetivamente
executa, do mesmo jeito que o terminal pede confirmação por texto ("s/n").

A edição de finanças/fãs/força segue a mesma regra do terminal: fica
bloqueada enquanto existir qualquer carreira em `saves/`. A trava é checada
tanto na tela (que não mostra o formulário) quanto no POST (que recusa), pra
não depender só do template.
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from persistencia import carregar_equipes, listar_saves, restaurar_equipes_padrao, salvar_equipes
from web.templates_config import templates

router = APIRouter(tags=["equipes"])

MENSAGEM_EDICAO_BLOQUEADA = (
    "Não é possível editar finanças/fãs/força com carreiras salvas em andamento. "
    "Esses valores só mudam automaticamente conforme o jogador avança na carreira salva."
)


def _times_do_campeonato(equipes, campeonato):
    times = equipes.get(campeonato)
    if times is None:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado.")
    return times


def _equipe_do_campeonato(times, nome_equipe):
    equipe = next((time for time in times if time == nome_equipe), None)
    if equipe is None:
        raise HTTPException(status_code=404, detail="Equipe não encontrada nesse campeonato.")
    return equipe


def _edicao_bloqueada():
    """Mesma trava de `menu.editar_equipes` (opção "e"): finanças/fãs/força
    só podem ser editadas enquanto não houver nenhuma carreira salva.
    """
    return bool(listar_saves())


def _contexto_campeonato(campeonato, times):
    return {
        "campeonato": campeonato,
        "times": times,
        "edicao_bloqueada": _edicao_bloqueada(),
        "mensagem_bloqueio": MENSAGEM_EDICAO_BLOQUEADA,
    }


def _contexto_edicao(campeonato, equipe, erros=None):
    return {
        "campeonato": campeonato,
        "equipe": equipe,
        "erros": erros or [],
        "edicao_bloqueada": _edicao_bloqueada(),
        "mensagem_bloqueio": MENSAGEM_EDICAO_BLOQUEADA,
    }


def _validar_inteiro(texto, rotulo, minimo, maximo=None):
    """Valida um número inteiro digitado no formulário com a mesma regra de
    `menu.escolher_valor`. Retorna `(valor, None)` se válido ou
    `(None, mensagem_de_erro)` caso contrário.
    """
    texto = texto.strip()
    # `isdigit()` sozinho aceita dígitos Unicode como "²" ou "①", que
    # `int()` não converte (ValueError -> 500). Exigir ASCII + decimal
    # garante que só "0"-"9" passam.
    if texto.isascii() and texto.isdecimal():
        valor = int(texto)
        if valor >= minimo and (maximo is None or valor <= maximo):
            return valor, None
    limite = f" e {maximo}" if maximo is not None else " ou mais"
    return None, f"{rotulo}: digite um número inteiro entre {minimo}{limite}."


@router.get("/equipes")
def tela_equipes(request: Request):
    """Lista os campeonatos disponíveis para editar o elenco."""
    equipes = carregar_equipes()
    return templates.TemplateResponse(request, "equipes.html", {"campeonatos": list(equipes.keys())})


# Precisa ser registrada antes de `/equipes/{campeonato}`, senão o caminho
# "/equipes/restaurar" seria capturado como um campeonato chamado "restaurar".
@router.get("/equipes/restaurar")
def confirmar_restauracao_equipes(request: Request):
    """Tela de confirmação exibida antes de restaurar o elenco padrão — ação
    destrutiva, espelhando a confirmação "s/n" que o terminal pede.
    """
    return templates.TemplateResponse(request, "equipes_confirmar_restauracao.html", {})


@router.post("/equipes/restaurar")
def restaurar_equipes(request: Request):
    """Sobrescreve `equipes.json` com os valores padrão — chamado só a partir
    da tela de confirmação. Sem trava por carreiras salvas (igual ao
    terminal): cada carreira guarda sua própria cópia dos times.
    """
    restaurar_equipes_padrao()
    return RedirectResponse(url=request.url_for("tela_equipes"), status_code=303)


@router.get("/equipes/{campeonato}")
def tela_equipes_campeonato(request: Request, campeonato: str):
    """Lista as equipes (elenco fixo) de um campeonato, com o link para
    editar finanças/fãs/força de cada uma.
    """
    equipes = carregar_equipes()
    times = _times_do_campeonato(equipes, campeonato)
    return templates.TemplateResponse(request, "equipes_campeonato.html", _contexto_campeonato(campeonato, times))


@router.get("/equipes/{campeonato}/{nome_equipe}/editar")
def tela_editar_equipe(request: Request, campeonato: str, nome_equipe: str):
    """Sub-tela de edição de finanças/fãs/força de uma equipe. Com carreiras
    salvas, mostra a mensagem de bloqueio no lugar do formulário.
    """
    equipes = carregar_equipes()
    times = _times_do_campeonato(equipes, campeonato)
    equipe = _equipe_do_campeonato(times, nome_equipe)
    return templates.TemplateResponse(request, "equipes_editar.html", _contexto_edicao(campeonato, equipe))


@router.post("/equipes/{campeonato}/{nome_equipe}/editar")
def editar_equipe(
    request: Request,
    campeonato: str,
    nome_equipe: str,
    financas: Annotated[str, Form()] = "",
    fas: Annotated[str, Form()] = "",
    forca: Annotated[str, Form()] = "",
):
    """Salva finanças/fãs/força de uma equipe, validando com as mesmas faixas
    do terminal (finanças e fãs >= 0, força entre 0 e 100). Recusa (403) se
    houver carreiras salvas, mesmo que o formulário seja enviado por fora da
    tela. Os campos têm default vazio para que um campo em branco caia na
    mesma mensagem de validação amigável em vez de um 422 genérico.
    """
    equipes = carregar_equipes()
    times = _times_do_campeonato(equipes, campeonato)
    equipe = _equipe_do_campeonato(times, nome_equipe)

    if _edicao_bloqueada():
        return templates.TemplateResponse(
            request, "equipes_editar.html", _contexto_edicao(campeonato, equipe), status_code=403
        )

    valor_financas, erro_financas = _validar_inteiro(financas, "Finanças", 0)
    valor_fas, erro_fas = _validar_inteiro(fas, "Fãs", 0)
    valor_forca, erro_forca = _validar_inteiro(forca, "Força", 0, 100)
    erros = [erro for erro in (erro_financas, erro_fas, erro_forca) if erro]
    if erros:
        return templates.TemplateResponse(
            request, "equipes_editar.html", _contexto_edicao(campeonato, equipe, erros), status_code=400
        )

    equipe.financas = valor_financas
    equipe.fas = valor_fas
    equipe.forca = valor_forca
    salvar_equipes(equipes)
    return RedirectResponse(
        url=request.url_for("tela_equipes_campeonato", campeonato=campeonato), status_code=303
    )
