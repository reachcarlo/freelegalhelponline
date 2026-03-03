"""Standard legal definitions for California employment discovery.

Per CCP 2030.060(e), specially defined terms must appear in ALL CAPITALS
wherever they are used. These definitions follow prevailing employment
litigation practice and mirror DISC-002's defined terms.

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from collections import OrderedDict


def standard_definitions(
    employee_name: str = "[EMPLOYEE NAME]",
    employer_name: str = "[EMPLOYER NAME]",
) -> OrderedDict[str, str]:
    """Return the standard employment discovery definitions.

    Args:
        employee_name: The employee party's name (substituted into
            the EMPLOYEE definition).
        employer_name: The employer party's name (substituted into
            the EMPLOYER definition).

    Returns:
        Ordered dict of {TERM: definition_text}. The order is the
        conventional order for California employment discovery.
    """
    return OrderedDict(
        [
            (
                "DOCUMENT",
                'A writing as defined in Evidence Code section 250, and includes '
                'the original or a copy of handwriting, typewriting, printing, '
                'photostats, photographs, electronically stored information, and '
                'every other means of recording upon any tangible thing and form '
                'of communicating or representation, including letters, words, '
                'pictures, sounds, or symbols, or combinations of them.',
            ),
            (
                "COMMUNICATION",
                'The transmittal of information in the form of facts, ideas, '
                'inquiries, or otherwise, between two or more PERSONS, whether '
                'orally, in writing, electronically, or by any other means.',
            ),
            (
                "PERSON",
                'A natural person, firm, association, organization, partnership, '
                'business, trust, limited liability company, corporation, or '
                'public entity.',
            ),
            (
                "YOU / YOUR",
                f'{employer_name}, and any agent, employee, representative, '
                'investigator, attorney, or other PERSON acting on YOUR behalf.',
            ),
            (
                "IDENTIFY (as to a person)",
                "State the PERSON's full name, last known ADDRESS, telephone "
                "number, and relationship to the parties in this action.",
            ),
            (
                "IDENTIFY (as to a document)",
                "State the type of DOCUMENT, its date, author(s), recipient(s), "
                "subject matter, and present location or custodian.",
            ),
            (
                "ADDRESS",
                "The street address, including city, state, and zip code.",
            ),
            (
                "EMPLOYEE",
                f'{employee_name}.',
            ),
            (
                "EMPLOYER",
                f'{employer_name}, and any parent, subsidiary, affiliated, or '
                'related entity.',
            ),
            (
                "EMPLOYMENT",
                'A relationship in which the EMPLOYEE provides services '
                'requested by or on behalf of the EMPLOYER, other than an '
                'independent contractor relationship.',
            ),
            (
                "ADVERSE EMPLOYMENT ACTION",
                'Any TERMINATION, suspension, demotion, reprimand, loss of pay, '
                'failure or refusal to hire, failure or refusal to promote, '
                'or other action or failure to act that materially and adversely '
                "affects the EMPLOYEE's rights or interests as alleged in the "
                'PLEADINGS.',
            ),
            (
                "TERMINATION",
                'The actual or constructive termination of EMPLOYMENT, including '
                'a discharge, firing, layoff, forced resignation, or completion '
                'of the term of an employment agreement.',
            ),
            (
                "PLEADINGS",
                'The original or most recent amended version of the complaint, '
                'answer, and cross-complaint in this action.',
            ),
            (
                "RELATING TO / CONCERNING",
                'Referring to, describing, evidencing, constituting, mentioning, '
                'or being in any way logically or factually connected with the '
                'matter described.',
            ),
            (
                "INCIDENT",
                'The circumstances and events surrounding the alleged adverse '
                'employment action(s), injury, or other occurrence giving rise '
                'to this action or proceeding.',
            ),
            (
                "HEALTH CARE PROVIDER",
                'Any PERSON referred to in Code of Civil Procedure section '
                '667.7(e)(3).',
            ),
        ]
    )


# Pre-built definitions for common configurations
DEFAULT_DEFINITIONS = standard_definitions()

# RFPD-specific production instructions (standard practice)
STANDARD_PRODUCTION_INSTRUCTIONS = (
    "In responding to these requests, you are to produce all responsive "
    "DOCUMENTS in your possession, custody, or control, including "
    "DOCUMENTS in the possession of your agents, employees, "
    "representatives, investigators, attorneys (to the extent not "
    "privileged), accountants, or other PERSONS acting on your behalf.\n\n"
    "If any DOCUMENT responsive to these requests has been lost, "
    "discarded, or destroyed, identify the DOCUMENT, describe its "
    "contents, state the date it was lost, discarded, or destroyed, "
    "the reason therefor, and identify all PERSONS with knowledge of "
    "the circumstances.\n\n"
    "DOCUMENTS shall be produced as they are kept in the usual course "
    "of business or organized and labeled to correspond with the "
    "categories in this demand, pursuant to Code of Civil Procedure "
    "section 2031.280.\n\n"
    "If a claim of privilege is made for any DOCUMENT, identify the "
    "DOCUMENT, state the nature of the privilege claimed, and provide "
    "sufficient information to evaluate the claim, pursuant to Code of "
    "Civil Procedure section 2031.240(b)."
)
