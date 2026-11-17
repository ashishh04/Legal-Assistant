"""Who may see what.

One rule set, shared by the document index and the case model, so the assistant can never
show more than the Power BI semantic model would. It mirrors the RLS roles in the pack's
Semantic_Model sheet, and also filters the intake tables (mailbox, intake forms, app store)
by country, which the pack's RLS table leaves unfiltered although D3's spec says country
roles see their own country only.
"""
from __future__ import annotations

from dataclasses import dataclass

CASE_GROUPS = ("Legal-UAE", "Legal-KSA", "Legal-MENA")
_GROUP_FOR_COUNTRY = {"UAE": "Legal-UAE", "KSA": "Legal-KSA"}  # every other country -> Legal-MENA


def group_for_country(country: str) -> str:
    return _GROUP_FOR_COUNTRY.get(country, "Legal-MENA")


@dataclass(frozen=True)
class Role:
    name: str
    case_groups: frozenset[str]
    documents: bool
    description: str
    can_edit: bool = True  # may update the cases it sees: fields, evidence (with documents), follow-ups


_ALL = frozenset(CASE_GROUPS)
ROLES: dict[str, Role] = {
    "Legal-UAE": Role("Legal-UAE", frozenset({"Legal-UAE"}), True, "UAE cases, their documents and UAE intake reports"),
    "Legal-KSA": Role("Legal-KSA", frozenset({"Legal-KSA"}), True, "KSA cases, their documents and KSA intake reports"),
    "Legal-MENA": Role(
        "Legal-MENA", frozenset({"Legal-MENA"}), True,
        "cases, documents and intake reports for Egypt, Jordan, Kuwait, Qatar, Oman, Turkey and India",
    ),
    "Legal-Ops": Role("Legal-Ops", _ALL, True, "all countries, all case data and all documents"),
    "Leadership": Role("Leadership", _ALL, True, "all countries, all case data and all documents"),
    "Procurement": Role("Procurement", _ALL, False, "case data for all countries, but no case documents", can_edit=False),
}
NO_ACCESS = Role("none", frozenset(), False, "no case data", can_edit=False)
ESCALATION_GROUPS = ("Legal-Ops",)  # also told when a deadline is overdue (they oversee deadlines across the team)


def role_for_group(entra_group: str) -> Role:
    return ROLES.get(entra_group, NO_ACCESS)  # unknown groups fail closed


@dataclass(frozen=True)
class Principal:
    user_id: str
    full_name: str
    job_title: str
    entra_group: str
    role: Role

    def sees_group(self, access_group: str) -> bool:
        return access_group in self.role.case_groups

    def sees_country(self, country: str) -> bool:
        return self.sees_group(group_for_country(country))

    @property
    def sees_documents(self) -> bool:
        return self.role.documents

    @property
    def can_edit(self) -> bool:
        return self.role.can_edit

    @property
    def scope_key(self) -> tuple[tuple[str, ...], bool]:
        """Everything that decides what this principal sees (used to cache filtered snapshots)."""
        return tuple(sorted(self.role.case_groups)), self.role.documents
