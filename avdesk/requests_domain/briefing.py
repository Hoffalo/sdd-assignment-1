"""The briefing a requester submits, and how it is assembled.

Builder: a briefing has a dozen core fields plus a type-dependent set of
answers, most of them optional. A constructor with that many parameters is
the Bloater smell (telescoping constructor), so the web form and the tests
both assemble briefings step by step. The Director holds ready-made presets,
used by tests and by anyone who needs a complete example briefing.
"""
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Mapping

Answer = str | tuple[str, ...]

REVIEWERS_QUESTION = "avaliadores"


@dataclass(frozen=True)
class Briefing:
    requester_name: str = ""
    requester_email: str = ""
    diretoria_id: int | None = None
    type_code: str = ""
    type_detail: str = ""
    title: str = ""
    campaign: str = ""
    for_conference: bool = False
    needed_by: date | None = None
    needed_by_reason: str = ""
    rush_reason: str = ""
    answers: Mapping[str, Answer] = field(default_factory=dict)

    @property
    def reviewers(self) -> tuple[str, ...]:
        raw = self.answers.get(REVIEWERS_QUESTION, "")
        return tuple(line.strip() for line in str(raw).splitlines() if line.strip())

    def keep_answers(self, keys: set[str]) -> "Briefing":
        """Drops answers the requester can no longer see: another type, or a follow-up whose trigger changed."""
        return replace(self, answers={k: v for k, v in self.answers.items() if k in keys})


class BriefingBuilder:
    def __init__(self):
        self._reset()

    def _reset(self) -> None:
        self._fields: dict = {}
        self._answers: dict[str, Answer] = {}

    def requester(self, name: str, email: str, diretoria_id: int | None) -> "BriefingBuilder":
        self._fields.update(requester_name=name, requester_email=email, diretoria_id=diretoria_id)
        return self

    def request_type(self, code: str, detail: str = "") -> "BriefingBuilder":
        self._fields.update(type_code=code, type_detail=detail)
        return self

    def title(self, title: str) -> "BriefingBuilder":
        self._fields["title"] = title
        return self

    def campaign(self, campaign: str) -> "BriefingBuilder":
        self._fields["campaign"] = campaign
        return self

    def for_conference(self, flag: bool = True) -> "BriefingBuilder":
        self._fields["for_conference"] = flag
        return self

    def deadline(self, needed_by: date | None, reason: str) -> "BriefingBuilder":
        self._fields.update(needed_by=needed_by, needed_by_reason=reason)
        return self

    def rush_reason(self, reason: str) -> "BriefingBuilder":
        self._fields["rush_reason"] = reason
        return self

    def answer(self, key: str, value: Answer) -> "BriefingBuilder":
        self._answers[key] = value
        return self

    def build(self) -> Briefing:
        briefing = Briefing(**self._fields, answers=dict(self._answers))
        self._reset()
        return briefing


class BriefingDirector:
    """Builder presets. Keyword overrides replace a core field or an answer by name."""

    _COMMON_ANSWERS: dict[str, Answer] = {
        "objetivo": "Que estudantes se sintam convidados a participar.",
        "mensagem_chave": "A conferência é para você.",
        "publicos": ("Universitários no exterior",),
        "tom": "Institucional",
        "referencia_tom": "Vídeo de abertura da conferência anterior.",
        "destinos": ("Instagram",),
        "instagram_principal": "@gobrasa",
        "formatos": ("Vertical 9:16",),
        "aprovadores": "Diretoria de Comunicação",
    }

    def __init__(self, builder: BriefingBuilder):
        self.builder = builder

    def teaser(self, needed_by: date, **overrides) -> Briefing:
        answers = {**self._COMMON_ANSWERS, "teaser_anuncio": "Abertura das inscrições"}
        return self._build("teaser", needed_by, answers, overrides)

    def social_video(self, needed_by: date, **overrides) -> Briefing:
        overrides.setdefault("type_detail", "Reel")
        return self._build("redes_sociais", needed_by, dict(self._COMMON_ANSWERS), overrides)

    def _build(self, type_code: str, needed_by: date, answers: dict, overrides: dict) -> Briefing:
        core = {
            "requester_name": "Pessoa Solicitante",
            "requester_email": "solicitante@gobrasa.org",
            "diretoria_id": 1,
            "type_detail": "",
            "title": "Vídeo de exemplo",
            "campaign": "",
            "for_conference": False,
            "needed_by_reason": "Data de lançamento",
            "rush_reason": "",
        }
        for key, value in overrides.items():
            (core if key in core else answers)[key] = value

        builder = (self.builder
                   .requester(core["requester_name"], core["requester_email"], core["diretoria_id"])
                   .request_type(type_code, core["type_detail"])
                   .title(core["title"])
                   .campaign(core["campaign"])
                   .for_conference(core["for_conference"])
                   .deadline(needed_by, core["needed_by_reason"])
                   .rush_reason(core["rush_reason"]))
        for key, value in answers.items():
            builder.answer(key, value)
        return builder.build()
