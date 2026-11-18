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
ADMIN_GROUP = "Platform-Admin"
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
    can_own: bool = True   # may own cases and follow-ups (counsel); the administrator changes cases but owns none
    admin: bool = False    # manages users, and may switch into another user's view of the portal


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
    ADMIN_GROUP: Role(ADMIN_GROUP, _ALL, True, "all countries, all case data and documents, and user administration",
                      can_own=False, admin=True),
}
# The roles the administrator can give a user (there is one administrator, configured on the server).
ASSIGNABLE_GROUPS = ("Legal-UAE", "Legal-KSA", "Legal-MENA", "Legal-Ops", "Leadership", "Procurement")
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
    acting_by: str | None = None        # the administrator who switched into this user's view, if any
    acting_by_name: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role.admin

    @property
    def actor_label(self) -> str:
        """Who to name in the audit trail: the user, or "<administrator> as <user>" after a switch."""
        return f"{self.acting_by_name} as {self.full_name}" if self.acting_by else self.full_name

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
