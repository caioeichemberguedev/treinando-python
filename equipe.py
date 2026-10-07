class Equipe:
    """Uma equipe do jogo: nome + atributos de carreira (finanças, fãs,
    títulos, força) + cores do escudo.

    `cores` é uma lista com as 3 cores principais do time (hex, ex.:
    "#E30613") ou None quando o time não tem cores cadastradas (ex.: save
    antigo); nesse caso a interface usa um escudo padrão.

    `id` é um inteiro único e imutável que identifica o time (como a chave
    primária de um banco de dados); o nome é só o que aparece na tela. É
    somente leitura (`equipe.id = 5` levanta `AttributeError`) e fica None
    quando o time não tem id cadastrado (ex.: save antigo, times de teste).

    Para exibição, se comporta como o nome (__str__/__format__/__len__), o
    que permite usá-la direto em f-strings e no placar alinhado do terminal.

    Igualdade e hash são pelo `id`, e só entre `Equipe`s: duas equipes com o
    mesmo id são iguais mesmo com nomes diferentes; comparar com `str`/`int`
    dá False. Equipes sem id (None) só são iguais a si mesmas (mesmo
    objeto), para dois times "sem id" nunca serem iguais por acaso.
    """

    FINANCAS_INICIAL = 10_000_000
    FAS_INICIAL = 100_000
    FORCA_INICIAL = 50

    PREMIO_VITORIA = 500_000
    FAS_POR_VITORIA = 5_000
    FAS_PERDIDOS_NA_ELIMINACAO = 1_000

    PREMIO_TITULO = 5_000_000
    FAS_POR_TITULO = 50_000

    def __init__(
        self,
        nome,
        financas=None,
        fas=None,
        titulos=0,
        forca=None,
        cores=None,
        id=None,
    ):
        self._id = id
        self.nome = nome
        self.financas = financas if financas is not None else self.FINANCAS_INICIAL
        self.fas = fas if fas is not None else self.FAS_INICIAL
        self.titulos = titulos
        self.forca = forca if forca is not None else self.FORCA_INICIAL
        self.cores = list(cores) if cores is not None else None

    @property
    def id(self):
        """Identificador fixo do time (somente leitura, sem setter)."""
        return self._id

    def registrar_vitoria(self):
        self.financas += self.PREMIO_VITORIA
        self.fas += self.FAS_POR_VITORIA

    def registrar_eliminacao(self):
        self.fas = max(0, self.fas - self.FAS_PERDIDOS_NA_ELIMINACAO)

    def sagrar_campea(self):
        self.titulos += 1
        self.financas += self.PREMIO_TITULO
        self.fas += self.FAS_POR_TITULO

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "financas": self.financas,
            "fas": self.fas,
            "titulos": self.titulos,
            "forca": self.forca,
            "cores": self.cores,
        }

    @classmethod
    def from_dict(cls, dados):
        if isinstance(dados, str):
            return cls(dados)
        return cls(
            dados["nome"],
            dados.get("financas"),
            dados.get("fas"),
            dados.get("titulos", 0),
            dados.get("forca"),
            dados.get("cores"),
            id=dados.get("id"),
        )

    def __str__(self):
        return self.nome

    def __repr__(self):
        return (
            f"Equipe({self.nome!r}, id={self.id!r}, financas={self.financas}, fas={self.fas}, "
            f"titulos={self.titulos}, forca={self.forca}, "
            f"cores={self.cores!r})"
        )

    def __format__(self, format_spec):
        return format(self.nome, format_spec)

    def __len__(self):
        return len(self.nome)

    def __eq__(self, outro):
        if not isinstance(outro, Equipe):
            return NotImplemented
        if self.id is None or outro.id is None:
            return self is outro
        return self.id == outro.id

    def __hash__(self):
        if self.id is None:
            return object.__hash__(self)
        return hash(self.id)
