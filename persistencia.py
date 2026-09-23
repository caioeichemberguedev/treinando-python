import os
import json

from equipe import Equipe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_EQUIPES = os.path.join(BASE_DIR, "equipes.json")
ARQUIVO_SALVO = os.path.join(BASE_DIR, "jogo_salvo.json")

EQUIPES_PADRAO = {
    "Copa do Brasil": [
        "São Paulo",
        "Palmeiras",
        "Corinthians",
        "Santos",
        "Flamengo",
        "Vasco",
        "Botafogo",
        "Fluminense",
        "Grêmio",
        "Internacional",
        "Cruzeiro",
        "Atlético-MG",
        "Bahia",
        "Vitória",
        "Athletico-PR",
        "Coritiba",
    ],
    "Copa do Mundo 2026": [
        "Brasil",
        "Argentina",
        "Uruguai",
        "Paraguai",
        "França",
        "Espanha",
        "Alemanha",
        "Inglaterra",
        "Itália",
        "Holanda",
        "Portugal",
        "Croácia",
        "Marrocos",
        "Bélgica",
        "Noruega",
        "Suíça",
    ],
}


def carregar_equipes():
    if os.path.exists(ARQUIVO_EQUIPES):
        with open(ARQUIVO_EQUIPES, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        return {
            campeonato: [Equipe.from_dict(time_dados) for time_dados in times]
            for campeonato, times in dados.items()
        }

    equipes = {campeonato: [Equipe(nome) for nome in nomes] for campeonato, nomes in EQUIPES_PADRAO.items()}
    salvar_equipes(equipes)
    return equipes


def salvar_equipes(equipes):
    dados = {campeonato: [equipe.to_dict() for equipe in times] for campeonato, times in equipes.items()}
    with open(ARQUIVO_EQUIPES, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def salvar_jogo(campeonato, time_escolhido, temporada, classificados, historico=None):
    dados = {
        "campeonato": campeonato,
        "time_escolhido": time_escolhido.to_dict(),
        "temporada": temporada,
        # None = temporada nova, ainda não sorteada
        "classificados": [equipe.to_dict() for equipe in classificados] if classificados is not None else None,
        "historico": historico or [],  # temporadas já concluídas nesta carreira
    }
    with open(ARQUIVO_SALVO, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def carregar_jogo_salvo():
    """Lê o save em disco e já reconstrói `time_escolhido`/`classificados`
    como objetos `Equipe`. Retorna None se não houver jogo salvo.
    """
    if not os.path.exists(ARQUIVO_SALVO):
        return None

    with open(ARQUIVO_SALVO, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    dados["time_escolhido"] = Equipe.from_dict(dados["time_escolhido"])
    if dados["classificados"] is not None:
        dados["classificados"] = [Equipe.from_dict(item) for item in dados["classificados"]]

    return dados
