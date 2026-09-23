class Equipe:
    """Uma equipe do jogo: nome + atributos de carreira (finanças, fãs, títulos).

    Se comporta como uma string (__str__/__format__/__len__/__eq__/__hash__)
    para poder ser usada nos mesmos lugares que hoje esperam o nome do time
    (chaveamento, placar, comparações), sem precisar espalhar `.nome` por
    todo o código.
    """

    FINANCAS_INICIAL = 10_000_000
    FAS_INICIAL = 100_000

    PREMIO_VITORIA = 500_000
    FAS_POR_VITORIA = 5_000
    FAS_PERDIDOS_NA_ELIMINACAO = 1_000

    PREMIO_TITULO = 5_000_000
    FAS_POR_TITULO = 50_000

    def __init__(self, nome, financas=None, fas=None, titulos=0):
        self.nome = nome
        self.financas = financas if financas is not None else self.FINANCAS_INICIAL
        self.fas = fas if fas is not None else self.FAS_INICIAL
        self.titulos = titulos

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
            "nome": self.nome,
            "financas": self.financas,
            "fas": self.fas,
            "titulos": self.titulos,
        }

    @classmethod
    def from_dict(cls, dados):
        if isinstance(dados, str):
            return cls(dados)
        return cls(dados["nome"], dados.get("financas"), dados.get("fas"), dados.get("titulos", 0))

    def __str__(self):
        return self.nome

    def __repr__(self):
        return f"Equipe({self.nome!r}, financas={self.financas}, fas={self.fas}, titulos={self.titulos})"

    def __format__(self, format_spec):
        return format(self.nome, format_spec)

    def __len__(self):
        return len(self.nome)

    def __eq__(self, outro):
        if isinstance(outro, Equipe):
            return self.nome == outro.nome
        if isinstance(outro, str):
            return self.nome == outro
        return NotImplemented

    def __hash__(self):
        return hash(self.nome)
