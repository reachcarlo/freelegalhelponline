"""Tests for DocumentClassifier (V2.1b.1)."""

from employee_help.casefile.classifiers import DocumentClassifier, DocumentType


class TestDocumentType:
    def test_enum_values(self):
        assert DocumentType.COMPLAINT.value == "complaint"
        assert DocumentType.ANSWER.value == "answer"
        assert DocumentType.DEMAND_LETTER.value == "demand_letter"
        assert DocumentType.PAY_STUB.value == "pay_stub"
        assert DocumentType.PERSONNEL.value == "personnel"
        assert DocumentType.EMAIL.value == "email"
        assert DocumentType.DISCOVERY.value == "discovery"
        assert DocumentType.GENERIC.value == "generic"


class TestClassifyComplaint:
    def setup_method(self):
        self.clf = DocumentClassifier()

    def test_california_complaint(self):
        text = """
        SUPERIOR COURT OF THE STATE OF CALIFORNIA
        COUNTY OF LOS ANGELES

        MARIA MARTINEZ,
            Plaintiff,
        vs.
        ACME CORPORATION, a California corporation; and DOES 1 through 50,
            Defendants.

        Case No. 24STCV12345

        COMPLAINT FOR DAMAGES

        GENERAL ALLEGATIONS

        1. Plaintiff alleges that at all times relevant herein, Plaintiff
        was employed by Defendant ACME CORPORATION as an Analyst in the
        Finance department.

        FIRST CAUSE OF ACTION
        (FEHA Discrimination — Gov. Code § 12940(a))

        2. Plaintiff incorporates by reference paragraphs 1 through 1 above.

        PRAYER FOR RELIEF

        WHEREFORE, Plaintiff prays for judgment as follows:
        1. General damages
        2. Special damages
        3. Punitive damages
        """
        assert self.clf.classify(text) == DocumentType.COMPLAINT

    def test_amended_complaint(self):
        text = """
        FIRST AMENDED COMPLAINT

        Plaintiff comes now and hereby complains against Defendant.

        GENERAL ALLEGATIONS

        Plaintiff alleges the following causes of action:

        FIRST CAUSE OF ACTION FOR wrongful termination.
        """
        assert self.clf.classify(text) == DocumentType.COMPLAINT

    def test_complaint_filename_hint(self):
        text = """
        The plaintiff was employed by defendant. Plaintiff alleges wrongful
        termination. DOES 1 through 50 are also named.
        """
        assert self.clf.classify(text, "complaint.pdf") == DocumentType.COMPLAINT


class TestClassifyAnswer:
    def setup_method(self):
        self.clf = DocumentClassifier()

    def test_answer_to_complaint(self):
        text = """
        ANSWER TO COMPLAINT

        Defendant hereby answers the Complaint filed by Plaintiff and
        denies each and every allegation contained therein.

        AFFIRMATIVE DEFENSES

        FIRST AFFIRMATIVE DEFENSE
        (Failure to State a Cause of Action)

        The Complaint, and each purported cause of action therein, fails
        to state facts sufficient to constitute a cause of action.

        SECOND AFFIRMATIVE DEFENSE
        (Statute of Limitations)

        Defendant lacks sufficient information and belief to form an
        opinion as to the truth of the allegations.

        GENERAL DENIAL

        Answering defendant denies generally and specifically each and
        every allegation in the complaint.
        """
        assert self.clf.classify(text) == DocumentType.ANSWER


class TestClassifyDemandLetter:
    def setup_method(self):
        self.clf = DocumentClassifier()

    def test_settlement_demand(self):
        text = """
        SETTLEMENT DEMAND

        Dear Counsel,

        This letter constitutes a pre-litigation demand on behalf of our
        client Maria Martinez against Acme Corporation.

        We hereby demand settlement in the amount of $450,000 for damages
        arising from the wrongful termination of Ms. Martinez.

        We are prepared to settle this matter in lieu of litigation if
        your client agrees to pay the statutory damages and penalties
        owed under California law.

        Settlement Demand: $450,000.00
        """
        assert self.clf.classify(text) == DocumentType.DEMAND_LETTER

    def test_demand_for_payment(self):
        text = """
        DEMAND FOR PAYMENT

        We hereby demand that you pay the outstanding wages owed to our
        client. This demand is made in lieu of filing a complaint with
        the Labor Commissioner.

        We demand payment of $25,000 in unpaid overtime.
        """
        assert self.clf.classify(text) == DocumentType.DEMAND_LETTER


class TestClassifyPayStub:
    def setup_method(self):
        self.clf = DocumentClassifier()

    def test_earnings_statement(self):
        text = """
        EARNINGS STATEMENT

        Employee: Maria Martinez        Employee ID: 12345
        Pay Period: 01/01/2025 - 01/15/2025
        Check Date: 01/20/2025          Check Number: 8899

        EARNINGS                  Hours    Rate       Amount
        Regular Hours             80.00    $36.06     $2,884.62
        Overtime Hours            12.00    $54.09     $  649.08

        DEDUCTIONS
        Federal Tax                                   $  520.00
        State Tax (CA)                                $  185.00
        Social Security (FICA)                        $  219.09
        Medicare                                      $   51.24

        Gross Pay:    $3,533.70
        Net Pay:      $2,558.37
        YTD Gross:    $3,533.70
        """
        assert self.clf.classify(text) == DocumentType.PAY_STUB


class TestClassifyPersonnel:
    def setup_method(self):
        self.clf = DocumentClassifier()

    def test_offer_letter(self):
        text = """
        OFFER OF EMPLOYMENT

        Dear Maria,

        We are pleased to offer you the position of Senior Analyst at
        Acme Corporation. Your base salary will be $95,000 annually,
        reporting to the Director of Finance.

        Your start date will be March 1, 2019. This is an at-will
        employment arrangement.

        Annual compensation: $95,000
        """
        assert self.clf.classify(text) == DocumentType.PERSONNEL

    def test_termination_letter(self):
        text = """
        TERMINATION NOTICE

        Dear Ms. Martinez,

        This letter is to inform you that your employment with Acme
        Corporation is hereby terminated effective November 15, 2025.

        Your last day of employment will be November 15, 2025.

        Severance: Two weeks of base salary.
        """
        assert self.clf.classify(text) == DocumentType.PERSONNEL

    def test_performance_review(self):
        text = """
        PERFORMANCE EVALUATION

        Employee Name: Maria Martinez
        Employee ID: 12345
        Review Period: January 2024 - December 2024
        Performance Rating: Meets Expectations

        Performance Goals:
        1. Complete quarterly reports on time — Met
        2. Reduce processing errors by 10% — Exceeded

        Corrective Action: None required
        Performance Score: 3.5/5.0
        """
        assert self.clf.classify(text) == DocumentType.PERSONNEL


class TestClassifyEmail:
    def setup_method(self):
        self.clf = DocumentClassifier()

    def test_email_headers(self):
        text = """From: manager@acme.com
To: maria.martinez@acme.com
Subject: RE: Performance Concerns
Date: Mon, 15 Sep 2025 10:30:00 -0700
CC: hr@acme.com

Maria,

I need to discuss some concerns about your recent performance.

Please meet me in my office at 2pm today.
"""
        assert self.clf.classify(text) == DocumentType.EMAIL

    def test_email_by_extension(self):
        text = "Some random text content without clear email headers."
        assert self.clf.classify(text, "message.eml") == DocumentType.EMAIL

    def test_msg_extension(self):
        text = "Outlook message content."
        assert self.clf.classify(text, "meeting.msg") == DocumentType.EMAIL

    def test_mbox_extension(self):
        text = "Mbox archive content."
        assert self.clf.classify(text, "export.mbox") == DocumentType.EMAIL


class TestClassifyDiscovery:
    def setup_method(self):
        self.clf = DocumentClassifier()

    def test_interrogatories(self):
        text = """
        SPECIAL INTERROGATORIES, SET NO. 1

        PROPOUNDING PARTY: Plaintiff MARIA MARTINEZ
        RESPONDING PARTY: Defendant ACME CORPORATION

        INTERROGATORY NO. 1:
        Please identify all persons who participated in the decision to
        terminate Plaintiff's employment.

        INTERROGATORY NO. 2:
        Please identify each and every document relating to Plaintiff's
        performance evaluations.

        Code of Civil Procedure Section 2030.
        """
        assert self.clf.classify(text) == DocumentType.DISCOVERY

    def test_request_for_production(self):
        text = """
        REQUEST FOR PRODUCTION OF DOCUMENTS, SET NO. 1

        PROPOUNDING PARTY: Plaintiff
        RESPONDING PARTY: Defendant

        REQUEST NO. 1:
        Produce all documents relating to Plaintiff's employment.

        REQUEST NO. 2:
        Produce all documents and communications regarding Plaintiff's
        termination, without waiving any objection.
        """
        assert self.clf.classify(text) == DocumentType.DISCOVERY


class TestClassifyGeneric:
    def setup_method(self):
        self.clf = DocumentClassifier()

    def test_empty_text(self):
        assert self.clf.classify("") == DocumentType.GENERIC

    def test_whitespace_only(self):
        assert self.clf.classify("   \n\t  ") == DocumentType.GENERIC

    def test_unrecognized_content(self):
        text = """
        Meeting notes from Q4 planning session.

        We discussed the roadmap for next year and agreed on the
        following priorities:
        1. Improve customer onboarding
        2. Launch mobile app
        3. Integrate with third-party tools
        """
        assert self.clf.classify(text) == DocumentType.GENERIC

    def test_low_signal_legal_text(self):
        text = "This is a legal document with some text but not enough cues."
        assert self.clf.classify(text) == DocumentType.GENERIC


class TestClassifierEdgeCases:
    def setup_method(self):
        self.clf = DocumentClassifier()

    def test_complaint_beats_answer_with_caption(self):
        """When both complaint and answer keywords appear, complaint with
        caption and stronger heading signals should win."""
        text = """
        SUPERIOR COURT OF CALIFORNIA

        MARIA MARTINEZ,
            Plaintiff,
        vs.
        ACME CORPORATION,
            Defendant.

        COMPLAINT FOR DAMAGES

        Plaintiff alleges and hereby complains:

        FIRST CAUSE OF ACTION

        Plaintiff incorporates by reference the general allegations.

        PRAYER FOR RELIEF
        General damages and special damages and punitive damages.
        """
        assert self.clf.classify(text) == DocumentType.COMPLAINT

    def test_answer_wins_over_complaint_when_stronger(self):
        """An answer document with strong answer signals should classify
        as answer even though it references the complaint."""
        text = """
        ANSWER TO COMPLAINT

        Defendant hereby answers the Complaint.

        Defendant denies each and every allegation.
        Defendant denies generally and specifically all claims.

        AFFIRMATIVE DEFENSES

        FIRST AFFIRMATIVE DEFENSE
        Defendant lacks sufficient information.

        SECOND AFFIRMATIVE DEFENSE
        Answering defendant asserts statute of limitations.

        THIRD AFFIRMATIVE DEFENSE
        Answering party asserts failure to mitigate.

        GENERAL DENIAL
        """
        assert self.clf.classify(text) == DocumentType.ANSWER

    def test_filename_tiebreaker(self):
        """Filename hint should help push a borderline document over the
        minimum score threshold."""
        text = (
            "Dear Ms. Martinez, your last day of employment will be "
            "November 15, 2025. Please return your employee ID badge."
        )
        result = self.clf.classify(text, "termination_letter.pdf")
        assert result == DocumentType.PERSONNEL
