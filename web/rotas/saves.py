"""Rotas de carreiras salvas: listar, carregar (continuar) e excluir uma
carreira específica.

Espelha `escolher_save`/`carregar_jogo`/exclusão do terminal (`menu.py`).
Carregar uma carreira copia os dados salvos para `web/estado.py` junto com o
`nome_save`, então a carreira continua sendo gravada no MESMO arquivo de
`saves/` enquanto se joga pela web (E-018). Carregar em si só grava quando
precisa sortear uma temporada nova, igual ao terminal.
Excluir uma carreira é uma ação destrutiva, então passa por uma tela de
confirmação antes do POST que efetivamente remove, do mesmo jeito que
`web/rotas/equipes.py` já faz para restaurar o elenco padrão.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from campeonato import sortear_classificados, unificar_time_escolhido
from persistencia import carregar_equipes, carregar_jogo_salvo, excluir_jogo_salvo, listar_saves
from web.estado import iniciar_jogo, salvar_jogo_em_andamento
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
    (mesmos detalhes exibidos por `menu.escolher_save`).
    """
    saves = [{"nome": nome, **carregar_jogo_salvo(nome)} for nome in listar_saves()]
    return templates.TemplateResponse(request, "saves.html", {"saves": saves})


@router.post("/saves/{nome_save}/carregar")
def carregar_save(nome_save: str):
    """Carrega uma carreira salva para dentro do estado em memória e segue
    para o dashboard da carreira (`/carreira`, E-019), de onde "Jogar
    próxima fase" leva à fase atual.

    O jogo em memória guarda o `nome_save` da URL, então as próximas
    gravações da web vão para o mesmo arquivo em `saves/`.

    Quando `classificados` é `None` (temporada nova ainda não sorteada),
    sorteia a partir do elenco base do campeonato e grava o sorteio no mesmo
    arquivo — igual `rodar_temporada` faz no terminal. Com `classificados`
    já preenchidos (carreira salva no meio da temporada), não grava nada.

    O roster completo do campeonato (`times`) é sempre recarregado aqui e
    guardado em `times_do_campeonato`, independente de `classificados` já vir
    preenchido ou não. O time do jogador é um objeto só em todo lugar
    (B-020): `carregar_jogo_salvo` já devolve o `time_escolhido` como o
    mesmo objeto do classificado, e aqui o roster é unificado com ele
    (`unificar_time_escolhido`) antes de sortear/guardar — então o sorteio
    de agora e o de `/campeao/continuar` usam o `time_escolhido` com os
    títulos da carreira. Os DEMAIS times do save continuam objetos
    reconstruídos à parte (via `Equipe.from_dict`), sem identidade com o
    roster recém-carregado — o mesmo split que existe no terminal em
    `menu.carregar_jogo`; só para carreiras iniciadas direto na web
    (`/novo-jogo/time`) a progressão dos adversários persiste entre
    temporadas dentro da mesma sessão.
    """
    dados = _dados_do_save_existente(nome_save)

    campeonato = dados["campeonato"]
    times = unificar_time_escolhido(dados["time_escolhido"], carregar_equipes().get(campeonato, []))
    classificados = dados["classificados"]
    sorteou = classificados is None
    if sorteou:
        if len(times) < 2:
            raise HTTPException(
                status_code=400,
                detail="Esse campeonato não tem equipes suficientes para a nova temporada.",
            )
        classificados = sortear_classificados(times)

    jogo = iniciar_jogo(
        campeonato,
        dados["time_escolhido"],
        dados["temporada"],
        classificados,
        historico=dados.get("historico", []),
        times_do_campeonato=times,
        nome_save=nome_save,
    )
    if sorteou:
        salvar_jogo_em_andamento(jogo, jogo.temporada, jogo.classificados)

    return RedirectResponse(url="/carreira", status_code=303)


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
