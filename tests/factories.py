"""Small, hand-made reference data so unit tests never depend on seed.json."""
from avdesk.requests_domain.models import Analyst, Catalog, Diretoria, Question, RequestType


def make_catalog() -> Catalog:
    return Catalog(
        types=(
            RequestType("teaser", "Teaser", 10, None),
            RequestType("redes_sociais", "Vídeo para redes sociais", 7, "Qual formato?"),
            RequestType("outro", "Outro", 10, "Descreva"),
        ),
        questions=(
            Question("objetivo", None, "Objetivo", "Objetivo?", "textarea", (), True),
            Question("tom", None, "Tom", "Tom?", "choice", ("Inspirador", "Institucional"), True),
            Question("roteiro_url", None, "Material", "Roteiro?", "url", (), False),
            Question("teaser_anuncio", "teaser", "Teaser", "Anuncia o quê?", "text", (), True),
            Question("outro_justificativa", "outro", "Outro", "Por quê?", "textarea", (), True),
        ),
        diretorias=(Diretoria(1, "Comunicação"), Diretoria(2, "Conferências")),
        analysts=(Analyst(1, "Analista AV 1"),),
    )
