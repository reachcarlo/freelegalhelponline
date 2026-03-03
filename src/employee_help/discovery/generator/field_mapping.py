"""PDF field mappings for Judicial Council discovery forms.

Maps domain model data to the exact AcroForm field names in
DISC-001 (Form Interrogatories — General), DISC-002 (Form
Interrogatories — Employment Law), and DISC-020 (Requests
for Admission).

Field names were extracted via PyPDFForm schema inspection.

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from .._compat import TypeAlias

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

FieldName: TypeAlias = str
FieldValue: TypeAlias = str | bool

# ---------------------------------------------------------------------------
# DISC-001 — Form Interrogatories (General)
# ---------------------------------------------------------------------------

# Header / case-info text fields
DISC001_HEADER_FIELDS: dict[str, FieldName] = {
    "court_county": "TextField4[0]",
    "short_title": "TextField8[0]",
    "asking_party": "TextField5[0]",
    "answering_party": "TextField6[0]",
    "set_number": "TextField7[0]",
    "case_number": "CaseNumber[0]",
    "attorney_name": "Name[0]",
    "attorney_sbn": "AttyBarNo[0]",
    "attorney_firm": "AttyFirm[0]",
    "attorney_street": "Street[0]",
    "attorney_city": "City[0]",
    "attorney_state": "State[0]",
    "attorney_zip": "Zip[0]",
    "attorney_phone": "Phone[0]",
    "attorney_fax": "Fax[0]",
    "attorney_email": "Email[0]",
    "attorney_for": "AttyFor[0]",
    "date": "DateField1[0]",
    "custom_definitions": "FillText36[0]",
}

# Section → checkbox field name.
# Keys use the JC section numbering (e.g. "1.1", "2.1", "6.3").
DISC001_SECTION_FIELDS: dict[str, FieldName] = {
    # Section 1 — Identity
    "1.1": "Identity[0]",
    # Section 2 — General Background (Individual)
    "2.1": "GenBkgrd[0]",
    "2.2": "GenBkgrd2[0]",
    "2.3": "GenBkgrd3[0]",
    "2.4": "GenBkgrd4[0]",
    "2.5": "GenBkgrd5[0]",
    "2.6": "GenBkgrd6[0]",
    "2.7": "GenBkgrd7[0]",
    "2.8": "GenBkgrd8[0]",
    "2.9": "GenBkgrd9[0]",
    "2.10": "GenBkgrd10[0]",
    "2.11": "GenBkgrd11[0]",
    "2.12": "GenBkgrd12[0]",
    "2.13": "GenBkgrd13[0]",
    # Section 3 — General Background (Entity)
    "3.1": "GenBkgrdBiz[0]",
    "3.2": "GenBkgrdBiz2[0]",
    "3.3": "GenBkgrdBiz3[0]",
    "3.4": "GenBkgrdBiz4[0]",
    "3.5": "GenBkgrdBiz5[0]",
    "3.6": "GenBkgrdBiz6[0]",
    "3.7": "GenBkgrdBiz7[0]",
    # Section 4 — Insurance
    "4.1": "Insurance[0]",
    "4.2": "Insurance2[0]",
    # Section 6 — Physical, Mental, Emotional Injuries
    "6.1": "PMEInjuries[0]",
    "6.2": "PMEInjuries2[0]",
    "6.3": "PMEInjuries3[0]",
    "6.4": "PMEInjuries4[0]",
    "6.5": "PMEInjuries5[0]",
    "6.6": "PMEInjuries6[0]",
    "6.7": "PMEInjuries7[0]",
    # Section 7 — Property Damage
    "7.1": "PropDam[0]",
    "7.2": "PropDam2[0]",
    "7.3": "PropDam3[0]",
    # Section 8 — Lost Income / Earning Capacity
    "8.1": "LostincomeEarn[0]",
    "8.2": "LostincomeEarn2[0]",
    "8.3": "LostincomeEarn3[0]",
    "8.4": "LostincomeEarn4[0]",
    "8.5": "LostincomeEarn5[0]",
    "8.6": "LostincomeEarn6[0]",
    "8.7": "LostincomeEarn7[0]",
    "8.8": "LostincomeEarn8[0]",
    # Section 9 — Other Damages
    "9.1": "OtherDam[0]",
    "9.2": "OtherDam2[0]",
    # Section 10 — Medical History
    "10.1": "MedHist[0]",
    "10.2": "MedHist2[0]",
    "10.3": "MedHist3[0]",
    # Section 11 — Other Claims / Previous Claims
    "11.1": "OthPrvClaims[0]",
    "11.2": "OthPrvClaims[0]",  # Same field name as 11.1 in the PDF
    # Section 12 — Investigation (General)
    "12.1": "InvestigatGen[0]",
    "12.2": "InvestigatGen2[0]",
    "12.3": "InvestigatGen3[0]",
    "12.4": "InvestigatGen[0]",  # Page 6 duplicate field name
    "12.5": "CheckBox34[0]",
    "12.6": "CheckBox35[0]",
    "12.7": "CheckBox36[0]",
    # Section 13 — Surveillance
    "13.1": "CheckBox37[0]",
    "13.2": "CheckBox38[0]",
    # Section 14 — Statutory / Regulatory Violation
    "14.1": "StatRegViolation[0]",
    "14.2": "StatRegViolation2[0]",
    # Section 15 — Denials and Affirmative Defenses
    "15.1": "DSADefenses[0]",
    # Section 16 — Defendant's Contentions
    "16.1": "DefContend[0]",
    "16.2": "DefContend2[0]",
    "16.3": "DefContend3[0]",
    "16.4": "DefContend4[0]",
    "16.5": "DefContend5[0]",
    "16.6": "DefContend6[0]",
    "16.7": "DefContend7[0]",
    "16.8": "DefContend8[0]",
    "16.9": "DefContend9[0]",
    "16.10": "DefContend10[0]",
    # Section 17 — Responses to Requests for Admission
    "17.1": "RespReqAd[0]",
    # Section 20 — Incident (Motor Vehicle)
    "20.1": "IncOccrdMV[0]",
    "20.2": "IncOccrdMV2[0]",
    "20.3": "IncOccrdMV3[0]",
    "20.4": "IncOccrdMV4[0]",
    "20.5": "IncOccrdMV5[0]",
    "20.6": "IncOccrdMV6[0]",
    "20.7": "IncOccrdMV7[0]",
    "20.8": "IncOccrdMV8[0]",
    "20.9": "IncOccrdMV9[0]",
    "20.10": "IncOccrdMV[0]",  # Page 8 duplicate field name
    "20.11": "IncOccrdMV11[0]",
    # Section 50 — Contract
    "50.1": "Contract[0]",
    "50.2": "Contract2[0]",
    "50.3": "Contract3[0]",
    "50.4": "Contract4[0]",
    "50.5": "Contract5[0]",
    "50.6": "Contract6[0]",
}

# Sections relevant to employment law cases (for guided selection).
DISC001_EMPLOYMENT_SECTIONS: set[str] = {
    "1.1",
    "2.1", "2.5", "2.6", "2.7", "2.11",
    "4.1", "4.2",
    "6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "6.7",
    "8.1", "8.2", "8.3", "8.4", "8.5", "8.6", "8.7", "8.8",
    "9.1", "9.2",
    "10.1", "10.2", "10.3",
    "11.1",
    "12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.7",
    "13.1", "13.2",
    "15.1",
    "16.1", "16.2", "16.3", "16.5", "16.6", "16.9", "16.10",
    "17.1",
}

# Human-readable section labels for UI display.
DISC001_SECTION_LABELS: dict[str, str] = {
    "1": "Identity of Respondent",
    "2": "General Background — Individual",
    "3": "General Background — Business Entity",
    "4": "Insurance",
    "6": "Physical, Mental, or Emotional Injuries",
    "7": "Property Damage",
    "8": "Loss of Income / Earning Capacity",
    "9": "Other Damages",
    "10": "Medical History",
    "11": "Other Claims and Previous Claims",
    "12": "Investigation — Loss of Evidence",
    "13": "Surveillance",
    "14": "Statutory or Regulatory Violations",
    "15": "Denials and Affirmative Defenses",
    "16": "Defendant's Contentions — Personal Injury",
    "17": "Response to Request for Admissions",
    "20": "How the Incident Occurred — Motor Vehicle",
    "50": "Contract",
}


# ---------------------------------------------------------------------------
# DISC-002 — Form Interrogatories (Employment Law)
# ---------------------------------------------------------------------------

# Header / case-info text fields (different layout from DISC-001)
DISC002_HEADER_FIELDS: dict[str, FieldName] = {
    "attorney_info": "AttyCity_ft[0]",  # Multi-line: name, SBN, address
    "attorney_phone": "Phone_ft[0]",
    "attorney_fax": "Fax_ft[0]",
    "attorney_email": "Email_ft[0]",
    "set_number": "TextField3[0]",
    "case_number": "TextField1[0]",
    "answering_party": "TextField2[0]",
    "date": "DateField1[0]",
    "adverse_actions_list": "FillText1[0]",
}

# Section → checkbox field name.
DISC002_SECTION_FIELDS: dict[str, FieldName] = {
    # Section 200 — Employment Relationship
    "200.1": "EmpRelAtWill[0]",
    "200.2": "EmpRelNotAtWill[0]",
    "200.3": "EmpRelAgree[0]",
    "200.4": "EmpRelDoc[0]",
    "200.5": "EmpRelCollBarg[0]",
    "200.6": "EmpRelOthrBiz[0]",
    # Section 201 — Adverse Employment Actions / Termination
    "201.1": "AdvEmpActTerm[0]",
    "201.2": "AdvEmpActPostTerm[0]",
    "201.3": "AdvEmpActAskPrty[0]",
    "201.4": "AdvEmpActPerf[0]",
    "201.5": "AdvEmpActHired[0]",
    "201.6": "AdvEmpActReplace[0]",
    "201.7": "AdvEmpActContact[0]",
    # Section 202 — Discrimination
    "202.1": "Discrim[0]",
    "202.2": "DiscrimFacts[0]",
    # Section 203 — Harassment
    "203.1": "Harassed[0]",
    # Section 204 — Disability Discrimination
    "204.1": "DisDiscrim[0]",
    "204.2": "DisDiscrimInjury[0]",
    "204.4": "DisDiscrimContact[0]",
    "204.5": "DisDiscrimAccomdn[0]",
    "204.6": "DisDiscrimComm[0]",
    "204.7": "DisDiscrimConsider[0]",
    # Section 205 — Wrongful Discharge / Public Policy
    "205.1": "DischgViol[0]",
    # Section 206 — Defamation
    "206.1": "Defame[0]",
    "206.2": "DefameRespon[0]",
    "206.3": "DefamePub[0]",
    # Section 207 — Internal / External Complaints
    "207.1": "IntComplaints[0]",
    "207.2": "IntComplaintsConduct[0]",
    # Section 208 — Government Complaints
    "208.1": "GovComplaints[0]",
    "208.2": "GovComplaintsEmprRes[0]",
    # Section 209 — Other Claims / Previous Actions
    "209.1": "OthClaimsEmplee[0]",
    "209.2": "OthClaimsEmpler[0]",
    # Section 210 — Loss of Income (Employee)
    "210.1": "LossIncomeEmpe[0]",
    "210.2": "LossIncomeEmpePast[0]",
    "210.3": "LossIncomeEmpeFuture[0]",
    "210.4": "LossIncomeEmpeMinimize[0]",
    "210.5": "LossIncomeEmpePurch[0]",
    "210.6": "LossIncomeOthEmp[0]",
    # Section 211 — Benefits / Lost Income (Employer)
    "211.1": "LossIncomeEmpr[0]",
    "211.2": "LossIncomeEmprMinimize[0]",
    "211.3": "LossIncomeEmprUnreason[0]",
    # Section 212 — Emotional / Physical Injuries (Employment)
    "212.1": "InjuriesEmpe[0]",
    "212.2": "InjuriesEmpeCurrent[0]",
    "212.3": "InjuriesEmpeOngoing[0]",
    "212.4": "InjuriesEmpeExam[0]",
    "212.5": "InjuriesEmpeMeds[0]",
    "212.6": "InjuriesEmpeOthExp[0]",
    "212.7": "InjuriesEmpefuture[0]",
    # Section 213 — Other Damages
    "213.1": "OthDam[0]",
    "213.2": "OthDamDocs[0]",
    # Section 214 — Insurance
    "214.1": "Insurance[0]",
    "214.2": "InsuranceSelf[0]",
    # Section 215 — Investigation
    "215.1": "InvestigationIntw[0]",
    "215.2": "InvestigationWritn[0]",
    # Section 216 — Affirmative Defenses
    "216.1": "AffirmDefenses[0]",
    # Section 217 — Responses to RFAs
    "217.1": "RespReq[0]",
}

# Human-readable section labels for UI display.
DISC002_SECTION_LABELS: dict[str, str] = {
    "200": "Employment Relationship",
    "201": "Adverse Employment Actions / Termination",
    "202": "Discrimination",
    "203": "Harassment",
    "204": "Disability Discrimination",
    "205": "Wrongful Discharge in Violation of Public Policy",
    "206": "Defamation",
    "207": "Internal / External Complaints",
    "208": "Government Agency Complaints",
    "209": "Other Claims / Previous Actions",
    "210": "Loss of Income / Benefits (Employee)",
    "211": "Loss of Income / Benefits (Employer Contentions)",
    "212": "Physical, Mental, or Emotional Injuries",
    "213": "Other Damages",
    "214": "Insurance",
    "215": "Investigation",
    "216": "Affirmative Defenses",
    "217": "Responses to Requests for Admission",
}


# ---------------------------------------------------------------------------
# DISC-020 — Requests for Admission (Cover Sheet)
# ---------------------------------------------------------------------------

DISC020_HEADER_FIELDS: dict[str, FieldName] = {
    "attorney_info": "TextField1[0]",  # Multi-line: name, SBN, address
    "attorney_phone": "Phone[0]",
    "attorney_fax": "Fax[0]",
    "attorney_email": "Email[0]",
    "attorney_for": "Attorney[0]",
    "court_county": "CrtCounty_ft[0]",
    "court_street": "Street_ft[0]",
    "court_mailing": "MailingAdd_ft[0]",
    "court_city_zip": "CityZip_ft[0]",
    "court_branch": "Branch_ft[0]",
    "case_number": "CaseNumber_ft[0]",
    "short_title": "Party1_ft[0]",
    "requesting_party": "FillText10[0]",
    "answering_party": "FillText11[0]",
    "set_number": "FillText12[0]",
    "date": "FillText5[0]",
    "typed_name": "FillText21[0]",
}

DISC020_CHECKBOX_FIELDS: dict[str, FieldName] = {
    "truth_of_facts": "CheckBox1[0]",
    "genuineness_of_documents": "CheckBox2[0]",
    "facts_listed": "CheckBox6[0]",
    "facts_continued_attachment": "CheckBox5[0]",
    "docs_genuine": "CheckBox4[0]",
    "docs_continued_attachment": "CheckBox3[0]",
}

DISC020_TEXT_FIELDS: dict[str, FieldName] = {
    "facts_text": "FillText18[0]",
    "docs_text": "FillText17[0]",
}


# ---------------------------------------------------------------------------
# All section numbers → human-readable interrogatory text (for UI tooltips)
# ---------------------------------------------------------------------------

DISC001_SECTION_DESCRIPTIONS: dict[str, str] = {
    "1.1": "State the name, ADDRESS, telephone number, and relationship to you of each PERSON who prepared or assisted in the preparation of the responses.",
    "2.1": "State your full name, current and former residences, birth date, Social Security number, driver's license number.",
    "2.2": "State the date and place of your birth.",
    "2.3": "At the time of the INCIDENT, did you have a driver's license?",
    "2.4": "At the time of the INCIDENT, did you have any other permit or license for the operation of a motor vehicle?",
    "2.5": "State your home and business addresses and telephone numbers.",
    "2.6": "State your present occupation and employer information.",
    "2.7": "State your educational background and degrees.",
    "2.8": "Have you ever been convicted of a felony?",
    "2.9": "Can you speak English with ease?",
    "2.10": "Can you read and write English with ease?",
    "2.11": "At the time of the INCIDENT were you acting as an agent or employee for any PERSON?",
    "2.12": "At the time of the INCIDENT did you or any other person have any physical, emotional, or mental disability or condition?",
    "2.13": "Within 24 hours before the INCIDENT did you or any person involved use any substances?",
    "3.1": "Are you a corporation?",
    "3.2": "Are you a partnership?",
    "3.3": "Are you a limited liability company?",
    "3.4": "Are you a joint venture?",
    "3.5": "Are you an unincorporated association?",
    "3.6": "Have you done business under a fictitious name during the past 10 years?",
    "3.7": "Within the past five years has any public entity registered or licensed your business?",
    "4.1": "Was there in effect any policy of insurance for the damages, claims, or actions arising from the INCIDENT?",
    "4.2": "Are you self-insured under any statute?",
    "6.1": "Do you attribute any physical, mental, or emotional injuries to the INCIDENT?",
    "6.2": "Identify each injury you attribute to the INCIDENT.",
    "6.3": "Do you still have any complaints that you attribute to the INCIDENT?",
    "6.4": "Did you receive consultation, examination, or treatment from a HEALTH CARE PROVIDER?",
    "6.5": "Have you taken any medication as a result of injuries attributed to the INCIDENT?",
    "6.6": "Are there any other medical services necessitated by the injuries?",
    "6.7": "Has any HEALTH CARE PROVIDER advised that you may require future or additional treatment?",
    "7.1": "Do you attribute any loss of or damage to a vehicle or other property?",
    "7.2": "Has a written estimate or evaluation been made for any item of property?",
    "7.3": "Has any item of property been repaired?",
    "8.1": "Do you attribute any loss of income or earning capacity to the INCIDENT?",
    "8.2": "State your name, address, occupation, and employer at the time of the INCIDENT.",
    "8.3": "State the last date before the INCIDENT that you worked for compensation.",
    "8.4": "State your monthly income at the time of the INCIDENT.",
    "8.5": "State the date you returned to work following the INCIDENT.",
    "8.6": "State the dates you did not work and for which you lost income.",
    "8.7": "State the total income you have lost to date.",
    "8.8": "Will you lose income in the future?",
    "9.1": "Are there any other damages that you attribute to the INCIDENT?",
    "9.2": "Do any DOCUMENTS support the existence or amount of any item of damages?",
    "10.1": "Before the INCIDENT did you have complaints or injuries involving the same body part?",
    "10.2": "List all physical, mental, and emotional disabilities immediately before the INCIDENT.",
    "10.3": "After the INCIDENT, did you sustain injuries of the kind for which you are claiming damages?",
    "11.1": "In the past 10 years have you filed an action for personal injuries, bodily injury, or wrongful death?",
    "11.2": "In the past 10 years have you made a written claim for workers' compensation?",
    "12.1": "State the name, ADDRESS, and telephone number of each witness to the INCIDENT.",
    "12.2": "Have you interviewed any individual concerning the INCIDENT?",
    "12.3": "Have you obtained a written or recorded statement concerning the INCIDENT?",
    "12.4": "Do you know of any photographs, films, or videotapes concerning the INCIDENT?",
    "12.5": "Do you know of any diagram, reproduction, or model concerning the INCIDENT?",
    "12.6": "Was a report made by any PERSON concerning the INCIDENT?",
    "12.7": "Have you inspected the scene of the INCIDENT?",
    "13.1": "Have you conducted surveillance of any individual involved?",
    "13.2": "Has a written report been prepared on the surveillance?",
    "14.1": "Do you contend any PERSON violated any statute, ordinance, or regulation?",
    "14.2": "Was any PERSON cited or charged with a violation?",
    "15.1": "Identify each denial of a material allegation and each special or affirmative defense.",
    "16.1": "Do you contend any PERSON other than you or plaintiff contributed to the INCIDENT?",
    "16.2": "Do you contend plaintiff was not injured in the INCIDENT?",
    "16.3": "Do you contend plaintiff's injuries were not caused by the INCIDENT?",
    "16.4": "Do you contend any services furnished by a HEALTH CARE PROVIDER were not due to the INCIDENT?",
    "16.5": "Do you contend any costs of medical services were not necessary or unreasonable?",
    "16.6": "Do you contend any loss of earnings was unreasonable or not caused by the INCIDENT?",
    "16.7": "Do you contend any property damage was not caused by the INCIDENT?",
    "16.8": "Do you contend any costs of property repair were unreasonable?",
    "16.9": "Do you have any documents concerning claims for personal injuries by a plaintiff?",
    "16.10": "Do you have any documents concerning plaintiff's physical/mental/emotional condition?",
    "17.1": "Is your response to each request for admission an unqualified admission?",
    "20.1": "State the facts of how the vehicle INCIDENT occurred.",
    "20.2": "For each vehicle involved in the INCIDENT, state details.",
    "20.3": "State the location where your trip began and your destination.",
    "20.4": "Describe the route from the beginning of your trip to the INCIDENT.",
    "20.5": "State the street, lane, and direction of travel for each vehicle.",
    "20.6": "Did the INCIDENT occur at an intersection?",
    "20.7": "Was there a traffic signal facing you at the time?",
    "20.8": "State how the INCIDENT occurred, giving speed, direction, and location.",
    "20.9": "Do you have information that a malfunction or defect caused the INCIDENT?",
    "20.10": "Do you have information that a malfunction or defect contributed to injuries?",
    "20.11": "State the name and ADDRESS of each owner of each vehicle involved.",
    "50.1": "For each agreement alleged in the pleadings, describe it.",
    "50.2": "Was there a breach of any agreement alleged?",
    "50.3": "Was performance of any agreement excused?",
    "50.4": "Was any agreement terminated by mutual agreement, release, or novation?",
    "50.5": "Is any agreement unenforceable?",
    "50.6": "Is any agreement ambiguous?",
}

DISC002_SECTION_DESCRIPTIONS: dict[str, str] = {
    "200.1": "Do you contend the EMPLOYMENT relationship was 'at will'?",
    "200.2": "Do you contend the EMPLOYMENT relationship was not 'at will'?",
    "200.3": "Do you contend the EMPLOYMENT relationship was governed by any agreement?",
    "200.4": "Was any part governed by written rules, guidelines, policies, or procedures?",
    "200.5": "Was any part covered by collective bargaining agreements?",
    "200.6": "Do you contend the parties were in a business relationship other than employment?",
    "201.1": "Was the EMPLOYEE involved in a TERMINATION?",
    "201.2": "Are there facts supporting TERMINATION discovered after the TERMINATION?",
    "201.3": "Were there any other ADVERSE EMPLOYMENT ACTIONS?",
    "201.4": "Was the TERMINATION or ADVERSE EMPLOYMENT ACTION based on job performance?",
    "201.5": "Was any PERSON hired to replace the EMPLOYEE?",
    "201.6": "Has any PERSON performed any of the EMPLOYEE's former job duties?",
    "201.7": "If failure to select the EMPLOYEE, was any other PERSON selected instead?",
    "202.1": "Do you contend any ADVERSE EMPLOYMENT ACTIONS were discriminatory?",
    "202.2": "State all facts upon which you base your contention of discrimination.",
    "203.1": "Do you contend you were unlawfully harassed in your employment?",
    "204.1": "Name and describe each disability alleged in the PLEADINGS.",
    "204.2": "Does the EMPLOYEE allege any injury or illness arising from EMPLOYMENT?",
    "204.4": "Did the EMPLOYER have information about the EMPLOYEE's disability?",
    "204.5": "Did the EMPLOYEE need any accommodation to perform job functions?",
    "204.6": "Were there any communications about possible accommodation?",
    "204.7": "What did the EMPLOYER consider doing to accommodate the EMPLOYEE?",
    "205.1": "Do you contend the EMPLOYER took ADVERSE EMPLOYMENT ACTION in violation of public policy?",
    "206.1": "Did the EMPLOYER's agents PUBLISH any of the allegedly defamatory statements?",
    "206.2": "State agents who responded to inquiries regarding the EMPLOYEE after TERMINATION.",
    "206.3": "State each post-TERMINATION statement PUBLISHED about EMPLOYEE.",
    "207.1": "Were there any internal written policies applying to the complaint?",
    "207.2": "Did the EMPLOYEE complain to the EMPLOYER about unlawful conduct?",
    "208.1": "Did the EMPLOYEE file a claim with any governmental agency?",
    "208.2": "Did the EMPLOYER respond to any governmental claim?",
    "209.1": "In the past 10 years has the EMPLOYEE filed a civil action against any employer?",
    "209.2": "In the past 10 years has any employee filed a civil action against the EMPLOYER?",
    "210.1": "Do you attribute any loss of income or benefits to ADVERSE EMPLOYMENT ACTION?",
    "210.2": "State total amount of income, benefits, or earning capacity lost to date.",
    "210.3": "Will you lose income in the future?",
    "210.4": "Have you attempted to minimize the amount of your lost income?",
    "210.5": "Have you purchased any benefits to replace those lost?",
    "210.6": "Have you obtained other employment since the ADVERSE EMPLOYMENT ACTION?",
    "211.1": "Identify each type of BENEFIT the EMPLOYEE would have been entitled to.",
    "211.2": "Do you contend the EMPLOYEE has not made reasonable efforts to minimize lost income?",
    "211.3": "Do you contend any lost income was unreasonable or not caused by the action?",
    "212.1": "Do you attribute any injuries to the ADVERSE EMPLOYMENT ACTION?",
    "212.2": "Identify each injury you attribute to the ADVERSE EMPLOYMENT ACTION.",
    "212.3": "Do you still have any complaints of injuries?",
    "212.4": "Did you receive consultation or treatment from a HEALTH CARE PROVIDER?",
    "212.5": "Have you taken any medication as a result of injuries?",
    "212.6": "Are there any other medical services?",
    "212.7": "Has any HEALTH CARE PROVIDER advised you may require future treatment?",
    "213.1": "Are there any other damages that you attribute to the action?",
    "213.2": "Do any DOCUMENTS support the existence or amount of damages?",
    "214.1": "Was there in effect any policy of insurance?",
    "214.2": "Are you self-insured under any statute?",
    "215.1": "Have you interviewed any individual concerning the ADVERSE EMPLOYMENT ACTION?",
    "215.2": "Have you obtained a written or recorded statement?",
    "216.1": "Identify each denial and each special or affirmative defense.",
    "217.1": "Is your response to each request for admission an unqualified admission?",
}
