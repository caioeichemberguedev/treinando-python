import os
import json
from datetime import date

from equipe import Equipe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_EQUIPES = os.path.join(BASE_DIR, "equipes.json")
DIR_SAVES = os.path.join(BASE_DIR, "saves")

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

    return restaurar_equipes_padrao()


def restaurar_equipes_padrao():
    """Recria o elenco (finanças, fãs, força e títulos) com os valores
    iniciais padrão e sobrescreve o `equipes.json`. Não afeta um jogo salvo
    em andamento, que mantém sua própria cópia dos times.
    """
    equipes = {campeonato: [Equipe(nome) for nome in nomes] for campeonato, nomes in EQUIPES_PADRAO.items()}
    salvar_equipes(equipes)
    return equipes


def salvar_equipes(equipes):
    dados = {campeonato: [equipe.to_dict() for equipe in times] for campeonato, times in equipes.items()}
    with open(ARQUIVO_EQUIPES, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def _caminho_save(nome_save):
    return os.path.join(DIR_SAVES, f"{nome_save}.json")


def gerar_nome_save():
    """Gera um nome único para uma nova carreira, no formato
    "numero_dia_mes_ano" (ex.: "1_23_09_2026"), permitindo que várias
    carreiras existam salvas ao mesmo tempo e sejam distinguidas facilmente.
    """
    maior_numero = 0
    if os.path.isdir(DIR_SAVES):
        for nome_arquivo in os.listdir(DIR_SAVES):
            prefixo = nome_arquivo.split("_", 1)[0]
            if prefixo.isdigit():
                maior_numero = max(maior_numero, int(prefixo))

    hoje = date.today()
    return f"{maior_numero + 1}_{hoje.day:02d}_{hoje.month:02d}_{hoje.year}"


def listar_saves():
    """Lista os nomes das carreiras salvas, da mais antiga para a mais nova."""
    if not os.path.isdir(DIR_SAVES):
        return []

    nomes = [nome_arquivo[:-5] for nome_arquivo in os.listdir(DIR_SAVES) if nome_arquivo.endswith(".json")]

    def numero_do_save(nome):
        prefixo = nome.split("_", 1)[0]
        return int(prefixo) if prefixo.isdigit() else 0

    return sorted(nomes, key=numero_do_save)


def salvar_jogo(nome_save, campeonato, time_escolhido, temporada, classificados, historico=None):
    dados = {
        "campeonato": campeonato,
        "time_escolhido": time_escolhido.to_dict(),
        "temporada": temporada,
        # None = temporada nova, ainda não sorteada
        "classificados": [equipe.to_dict() for equipe in classificados] if classificados is not None else None,
        "historico": historico or [],  # temporadas já concluídas nesta carreira
    }
    os.makedirs(DIR_SAVES, exist_ok=True)
    with open(_caminho_save(nome_save), "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def carregar_jogo_salvo(nome_save):
    """Lê uma carreira salva específica e já reconstrói `time_escolhido`/
    `classificados` como objetos `Equipe`. Retorna None se não existir.
    """
    caminho = _caminho_save(nome_save)
    if not os.path.exists(caminho):
        return None

    with open(caminho, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    dados["time_escolhido"] = Equipe.from_dict(dados["time_escolhido"])
    if dados["classificados"] is not None:
        dados["classificados"] = [Equipe.from_dict(item) for item in dados["classificados"]]

    return dados


def excluir_jogo_salvo(nome_save):
    """Apaga uma carreira salva específica. Retorna True se ela existia."""
    caminho = _caminho_save(nome_save)
    if not os.path.exists(caminho):
        return False
    os.remove(caminho)
    return True
