"""Rotas de carreiras salvas: listar, carregar (continuar) e excluir uma
carreira específica.

Espelha `escolher_save`/`carregar_jogo`/exclusão do terminal (`menu.py`).
Carregar uma carreira COPIA os dados salvos para `web/estado.py` — nada é
regravado em `saves/` enquanto se joga pela web (decisão do ID-001,
reafirmada no ID-002: o "jogo em andamento" continua só em memória).
Excluir uma carreira é uma ação destrutiva, então passa por uma tela de
confirmação antes do POST que efetivamente remove, do mesmo jeito que
`web/rotas/equipes.py` já faz para restaurar o elenco padrão.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from campeonato import sortear_classificados
from persistencia import carregar_equipes, carregar_jogo_salvo, excluir_jogo_salvo, listar_saves
from web.estado import iniciar_jogo
from web.templates_config import templates

router = APIRouter(tags=["saves"])


def _dados_do_save_existente(nome_save: str) -> dict:
    dados = carregar_jogo_salvo(nome_save)
    if dados is None:
        raise HTTPException(status_code=404, detail="Carreira salva não encontrada.")
    return dados


@router.get("/saves")
def tela_saves(request: Request):
    """Lista as carreiras salvas, com time/campeonato/temporada de cada uma
    (mesmos detalhes exibidos por `menu.escolher_save`)."""
    saves = [{"nome": nome, **carregar_jogo_salvo(nome)} for nome in listar_saves()]
    return templates.TemplateResponse(request, "saves.html", {"saves": saves})


@router.post("/saves/{nome_save}/carregar")
def carregar_save(nome_save: str):
    """Carrega uma carreira salva para dentro do estado em memória e segue
    para a fase atual (`/fase`), reaproveitando o fluxo já existente do
    ID-001.

    Quando `classificados` é `None` (temporada nova ainda não sorteada),
    sorteia a partir do elenco base do campeonato — igual `rodar_temporada`
    faz no terminal.

    O roster completo do campeonato (`times`) é sempre recarregado aqui e
    guardado em `times_do_campeonato`, independente de `classificados` já vir
    preenchido ou não — mas, como o save guarda `classificados` como objetos
    `Equipe` reconstruídos à parte (via `Equipe.from_dict`), eles não
    compartilham identidade com esse roster recém-carregado. É o mesmo split
    de identidade que já existe hoje no terminal entre `dados["classificados"]`
    e `equipes[campeonato]` em `menu.carregar_jogo` — não é uma regressão
    nova: só para carreiras iniciadas direto na web (`/novo-jogo/time`) que a
    progressão de fato persiste entre temporadas dentro da mesma sessão.
    """
    dados = _dados_do_save_existente(nome_save)

    campeonato = dados["campeonato"]
    times = carregar_equipes().get(campeonato, [])
    classificados = dados["classificados"]
    if classificados is None:
        if len(times) < 2:
            raise HTTPException(
                status_code=400,
                detail="Esse campeonato não tem equipes suficientes para a nova temporada.",
            )
        classificados = sortear_classificados(times)

    iniciar_jogo(
        campeonato,
        dados["time_escolhido"],
        dados["temporada"],
        classificados,
        historico=dados.get("historico", []),
        times_do_campeonato=times,
    )

    return RedirectResponse(url="/fase", status_code=303)


@router.get("/saves/{nome_save}/excluir")
def confirmar_exclusao_save(request: Request, nome_save: str):
    """Tela de confirmação exibida antes de excluir uma carreira de verdade —
    ação destrutiva, espelhando a confirmação "s/n" que o terminal pede.
    """
    _dados_do_save_existente(nome_save)
    return templates.TemplateResponse(request, "saves_confirmar_exclusao.html", {"nome_save": nome_save})


@router.post("/saves/{nome_save}/excluir")
def excluir_save(nome_save: str):
    """Exclui a carreira definitivamente — chamado só a partir da tela de
    confirmação (`confirmar_exclusao_save`).
    """
    if not excluir_jogo_salvo(nome_save):
        raise HTTPException(status_code=404, detail="Carreira salva não encontrada.")
    return RedirectResponse(url="/saves", status_code=303)
