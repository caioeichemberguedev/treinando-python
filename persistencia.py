import os
import json
from datetime import date

from equipe import Equipe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_EQUIPES = os.path.join(BASE_DIR, "equipes.json")
DIR_SAVES = os.path.join(BASE_DIR, "saves")

# Fonte da verdade do elenco padrão: nome de cada time + as 3 cores do
# escudo (hex). Times de 2 cores repetem uma. O `equipes.json` é regenerado
# a partir daqui por `restaurar_equipes_padrao()`.
EQUIPES_PADRAO = {
    "Copa do Brasil": {
        "São Paulo": ["#E30613", "#FFFFFF", "#000000"],
        "Palmeiras": ["#006437", "#FFFFFF", "#006437"],
        "Corinthians": ["#000000", "#FFFFFF", "#000000"],
        "Santos": ["#FFFFFF", "#000000", "#FFFFFF"],
        "Flamengo": ["#C4161C", "#000000", "#C4161C"],
        "Vasco": ["#000000", "#FFFFFF", "#E30613"],
        "Botafogo": ["#000000", "#FFFFFF", "#000000"],
        "Fluminense": ["#870A28", "#FFFFFF", "#00613C"],
        "Grêmio": ["#0D80BF", "#000000", "#FFFFFF"],
        "Internacional": ["#E5050F", "#FFFFFF", "#E5050F"],
        "Cruzeiro": ["#2F529E", "#FFFFFF", "#2F529E"],
        "Atlético-MG": ["#000000", "#FFFFFF", "#000000"],
        "Bahia": ["#006CB5", "#FFFFFF", "#ED3237"],
        "Vitória": ["#E30613", "#000000", "#E30613"],
        "Athletico-PR": ["#C8102E", "#000000", "#C8102E"],
        "Coritiba": ["#00573F", "#FFFFFF", "#00573F"],
    },
    "Copa do Mundo 2026": {
        "Brasil": ["#009C3B", "#FFDF00", "#002776"],
        "Argentina": ["#75AADB", "#FFFFFF", "#75AADB"],
        "Uruguai": ["#55B5E5", "#FFFFFF", "#000000"],
        "Paraguai": ["#D52B1E", "#FFFFFF", "#0038A8"],
        "França": ["#002395", "#FFFFFF", "#ED2939"],
        "Espanha": ["#AA151B", "#F1BF00", "#AA151B"],
        "Alemanha": ["#000000", "#DD0000", "#FFCE00"],
        "Inglaterra": ["#FFFFFF", "#CE1124", "#FFFFFF"],
        "Itália": ["#009246", "#FFFFFF", "#CE2B37"],
        "Holanda": ["#F36C21", "#FFFFFF", "#21468B"],
        "Portugal": ["#006600", "#DA291C", "#FFCC00"],
        "Croácia": ["#FF0000", "#FFFFFF", "#171796"],
        "Marrocos": ["#C1272D", "#006233", "#C1272D"],
        "Bélgica": ["#000000", "#FDDA24", "#EF3340"],
        "Noruega": ["#BA0C2F", "#FFFFFF", "#00205B"],
        "Suíça": ["#DA291C", "#FFFFFF", "#DA291C"],
    },
}


def cores_do_time(nome):
    """Devolve uma cópia das 3 cores do time no elenco padrão, procurando o
    nome em todos os campeonatos, ou None se o time não estiver cadastrado.
    Aceita `Equipe` ou string.
    """
    nome = str(nome)
    for times in EQUIPES_PADRAO.values():
        if nome in times:
            return list(times[nome])
    return None


def carregar_equipes():
    if os.path.exists(ARQUIVO_EQUIPES):
        with open(ARQUIVO_EQUIPES, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        equipes = {
            campeonato: [Equipe.from_dict(time_dados) for time_dados in times]
            for campeonato, times in dados.items()
        }
        # `equipes.json` antigo (sem `cores`): completa só em memória com o
        # catálogo do elenco padrão, sem regravar o arquivo.
        for times in equipes.values():
            for equipe in times:
                if equipe.cores is None:
                    equipe.cores = cores_do_time(equipe.nome)
        return equipes

    return restaurar_equipes_padrao()


def restaurar_equipes_padrao():
    """Recria o elenco (finanças, fãs, força, títulos e cores) com os valores
    iniciais padrão e sobrescreve o `equipes.json`. Não afeta um jogo salvo
    em andamento, que mantém sua própria cópia dos times.
    """
    equipes = {
        campeonato: [Equipe(nome, cores=cores) for nome, cores in times.items()]
        for campeonato, times in EQUIPES_PADRAO.items()
    }
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
