/**
 * Claim-type definitions for SEO landing pages.
 * Each claim targets high-intent search queries (e.g., "do I have a wrongful termination case California").
 */

export interface ClaimFAQ {
  question: string;
  answer: string;
}

export interface ClaimDeadline {
  name: string;
  period: string;
  statute: string;
  notes?: string;
}

export interface ClaimElement {
  element: string;
  description: string;
}

export interface ClaimType {
  slug: string;
  title: string;
  shortTitle: string;
  description: string;
  metaDescription: string;
  overview: string;
  elements: ClaimElement[];
  deadlines: ClaimDeadline[];
  relevantStatutes: string[];
  primaryAgencies: string[];
  relatedClaimSlugs: string[];
  relatedTopicSlugs: string[];
  ctaQuery: string;
  faqs: ClaimFAQ[];
}

export const claims: ClaimType[] = [
  {
    slug: "wrongful-termination",
    title: "Wrongful Termination in California",
    shortTitle: "Wrongful Termination",
    description:
      "California wrongful termination claims for firings that violate public policy, breach implied contracts, or involve fraud.",
    metaDescription:
      "Do you have a wrongful termination case in California? Learn about the Tameny doctrine, at-will exceptions, filing deadlines, and your legal options. Free AI-powered guidance.",
    overview:
      "Although California is an at-will employment state, employers cannot fire employees for reasons that violate public policy. The landmark case Tameny v. Atlantic Richfield Co. (1980) established that an employee fired in violation of a fundamental public policy may sue for wrongful termination in violation of public policy (also called a 'Tameny claim'). Common examples include firing an employee for refusing to commit an illegal act, reporting legal violations, exercising a statutory right, or performing a statutory obligation like jury duty.",
    elements: [
      {
        element: "Employment relationship",
        description:
          "You were an employee (not an independent contractor) of the defendant employer.",
      },
      {
        element: "Termination",
        description:
          "Your employment was terminated, or you were constructively discharged (forced to resign due to intolerable conditions).",
      },
      {
        element: "Public policy violation",
        description:
          "The termination violated a fundamental public policy that is (1) delineated in a constitutional or statutory provision, (2) public in nature, (3) well-established at the time of discharge, and (4) substantial and fundamental.",
      },
      {
        element: "Causation",
        description:
          "The public-policy-violating reason was a substantial motivating factor in your termination.",
      },
      {
        element: "Damages",
        description:
          "You suffered harm (lost wages, emotional distress, etc.) as a result of the wrongful termination.",
      },
    ],
    deadlines: [
      {
        name: "Wrongful termination tort",
        period: "2 years",
        statute: "Code Civ. Proc. § 335.1",
        notes: "From the date of termination.",
      },
      {
        name: "FEHA-based wrongful termination",
        period: "3 years",
        statute: "Gov. Code § 12960",
        notes:
          "If the termination also involves FEHA-protected discrimination, file with CRD within 3 years.",
      },
      {
        name: "Breach of implied contract",
        period: "2 years (oral) / 4 years (written)",
        statute: "Code Civ. Proc. §§ 339, 337",
        notes:
          "If the claim is based on breach of an implied or express employment contract.",
      },
    ],
    relevantStatutes: [
      "Code Civ. Proc. § 335.1",
      "Lab. Code § 1102.5",
      "Lab. Code § 232.5",
      "Gov. Code § 12940",
    ],
    primaryAgencies: ["CRD", "DIR"],
    relatedClaimSlugs: [
      "feha-discrimination",
      "retaliation",
      "feha-harassment",
    ],
    relatedTopicSlugs: [
      "discrimination-and-harassment",
      "retaliation-and-whistleblower",
      "complaint-and-claims-process",
    ],
    ctaQuery: "Ask About Your Wrongful Termination Rights",
    faqs: [
      {
        question:
          "Can I sue for wrongful termination if I am an at-will employee in California?",
        answer:
          "Yes. While California is an at-will state, the at-will doctrine has important exceptions. You cannot be fired for reasons that violate public policy — such as refusing to break the law, reporting illegal activity (whistleblowing), exercising a legal right (like filing a workers' comp claim), or based on discrimination against a protected class. If your termination falls into one of these categories, you may have a wrongful termination claim regardless of your at-will status.",
      },
      {
        question: "What is a Tameny claim?",
        answer:
          "A Tameny claim — named after the California Supreme Court case Tameny v. Atlantic Richfield Co. (1980) — is a tort action for wrongful termination in violation of public policy. To succeed, you must show that your firing violated a public policy that is grounded in a statute or constitutional provision, benefits the public (not just you), and is well-established. Tameny claims allow recovery of compensatory damages, emotional distress damages, and potentially punitive damages.",
      },
      {
        question:
          "What damages can I recover in a wrongful termination case?",
        answer:
          "Damages may include: lost wages and benefits (past and future), emotional distress damages, punitive damages if the employer's conduct was malicious or oppressive, attorney's fees in certain statutory claims, and in some cases reinstatement. The specific damages available depend on the legal theory — tort claims (Tameny) allow broader damages including punitive damages, while contract claims are generally limited to economic losses.",
      },
      {
        question:
          "How long do I have to file a wrongful termination lawsuit in California?",
        answer:
          "The statute of limitations depends on the legal theory. For a wrongful termination tort (Tameny claim), you have 2 years from the date of termination under Code of Civil Procedure § 335.1. If the claim involves FEHA discrimination, you must file with the Civil Rights Department within 3 years, then have 1 year after receiving a right-to-sue notice. Breach of contract claims have 2-year (oral) or 4-year (written) deadlines. Act promptly — missing a deadline bars your claim.",
      },
      {
        question:
          "What is constructive discharge and does it count as wrongful termination?",
        answer:
          "Constructive discharge occurs when your employer makes your working conditions so intolerable that a reasonable person in your position would feel compelled to resign. Under California law, constructive discharge is treated the same as an actual firing for wrongful termination purposes. You must show the employer either intentionally created intolerable conditions or knowingly permitted them. Examples include severe harassment, demotion to humiliating duties, or a drastic pay cut in retaliation for protected activity.",
      },
    ],
  },
  {
    slug: "feha-discrimination",
    title: "FEHA Employment Discrimination in California",
    shortTitle: "FEHA Discrimination",
    description:
      "California FEHA discrimination claims covering protected classes, adverse employment actions, and the burden-shifting framework.",
    metaDescription:
      "Were you discriminated against at work in California? Learn about FEHA protected classes, how to prove discrimination, CRD filing deadlines, and available remedies. Free AI guidance.",
    overview:
      "The California Fair Employment and Housing Act (FEHA) prohibits employment discrimination based on over 20 protected characteristics including race, sex, age, disability, religion, sexual orientation, and national origin. FEHA applies to employers with 5 or more employees and covers all aspects of employment — hiring, firing, promotion, compensation, and terms and conditions. California courts apply the McDonnell Douglas burden-shifting framework: once an employee establishes a prima facie case, the burden shifts to the employer to articulate a legitimate, non-discriminatory reason, and then back to the employee to show that reason is pretextual.",
    elements: [
      {
        element: "Protected class membership",
        description:
          "You belong to a protected class under FEHA (race, color, national origin, ancestry, religion, sex, gender, gender identity, sexual orientation, marital status, age 40+, disability, medical condition, genetic information, military/veteran status, or reproductive health decision-making).",
      },
      {
        element: "Qualified for the position",
        description:
          "You were qualified to perform the essential functions of your job, with or without reasonable accommodation.",
      },
      {
        element: "Adverse employment action",
        description:
          "You suffered an adverse employment action — termination, demotion, failure to promote, reduction in pay, or a materially adverse change in the terms and conditions of employment.",
      },
      {
        element: "Discriminatory motive",
        description:
          "Your protected characteristic was a substantial motivating factor in the adverse action. This can be shown through direct evidence (discriminatory statements) or circumstantial evidence (similarly situated comparators treated better, suspicious timing, shifting explanations).",
      },
    ],
    deadlines: [
      {
        name: "CRD administrative complaint",
        period: "3 years",
        statute: "Gov. Code § 12960",
        notes: "From the date of the discriminatory act. File with the Civil Rights Department.",
      },
      {
        name: "Right-to-sue lawsuit",
        period: "1 year",
        statute: "Gov. Code § 12965(c)(1)(C)",
        notes:
          "After receiving a right-to-sue notice from CRD, you have 1 year to file a civil lawsuit.",
      },
    ],
    relevantStatutes: [
      "Gov. Code §§ 12900–12996",
      "Gov. Code § 12940",
      "Gov. Code § 12960",
      "Gov. Code § 12965",
    ],
    primaryAgencies: ["CRD"],
    relatedClaimSlugs: [
      "feha-harassment",
      "wrongful-termination",
      "retaliation",
    ],
    relatedTopicSlugs: [
      "discrimination-and-harassment",
      "complaint-and-claims-process",
      "leave-and-time-off",
    ],
    ctaQuery: "Ask About Your Discrimination Claim",
    faqs: [
      {
        question: "What is employment discrimination under FEHA?",
        answer:
          "Employment discrimination under FEHA occurs when an employer takes an adverse action against an employee or applicant because of a protected characteristic. FEHA covers the full employment lifecycle — hiring, compensation, promotion, job assignments, training, benefits, and termination. Unlike federal Title VII which requires 15+ employees, FEHA applies to employers with just 5 or more employees, providing broader coverage for California workers.",
      },
      {
        question: "How do I prove discrimination if there is no direct evidence?",
        answer:
          "Most discrimination cases rely on circumstantial evidence using the McDonnell Douglas burden-shifting framework. You establish a prima facie case by showing: (1) you belong to a protected class, (2) you were qualified, (3) you suffered an adverse action, and (4) circumstances suggest discrimination (e.g., replaced by someone outside your class). The employer must then provide a legitimate reason, and you can show that reason is a pretext for discrimination through evidence like inconsistent treatment, changing explanations, statistical patterns, or discriminatory remarks.",
      },
      {
        question: "What damages are available in a FEHA discrimination case?",
        answer:
          "FEHA provides broad remedies including: back pay and lost benefits, front pay (future lost earnings), compensatory damages for emotional distress, punitive damages for malice or reckless indifference, reasonable attorney's fees and litigation costs, and injunctive relief (policy changes, training). Unlike federal Title VII, California does not cap compensatory or punitive damages in FEHA cases, which can result in substantially larger awards.",
      },
      {
        question: "Can I file a FEHA claim without hiring a lawyer?",
        answer:
          "Yes. You can file a complaint with the Civil Rights Department (CRD) without an attorney. CRD offers online filing at calcivilrights.ca.gov. You may also request an immediate right-to-sue notice if you prefer to file a civil lawsuit. However, discrimination cases often involve complex legal issues, and many employment attorneys offer free consultations and work on contingency (no fee unless you win).",
      },
      {
        question:
          "Does FEHA protect independent contractors from discrimination?",
        answer:
          "FEHA's harassment protections apply to independent contractors, volunteers, and unpaid interns — not just employees. However, FEHA's discrimination protections (adverse employment actions) generally apply only to employees. If you are misclassified as an independent contractor but are actually an employee under California's ABC test, you would have full FEHA discrimination protections as an employee.",
      },
    ],
  },
  {
    slug: "feha-harassment",
    title: "Workplace Harassment Claims in California (FEHA)",
    shortTitle: "Workplace Harassment",
    description:
      "California FEHA harassment claims including hostile work environment and quid pro quo harassment.",
    metaDescription:
      "Experiencing workplace harassment in California? Learn about hostile work environment, quid pro quo harassment, employer liability, and how to file a FEHA complaint. Free AI guidance.",
    overview:
      "California's FEHA prohibits workplace harassment based on any protected characteristic. There are two types: hostile work environment harassment (unwelcome conduct that is severe or pervasive enough to alter working conditions) and quid pro quo harassment (employment benefits conditioned on submitting to unwelcome conduct). Importantly, FEHA harassment protections apply to all employers regardless of size — there is no minimum employee threshold. Individual harassers can also be held personally liable, unlike discrimination claims which only hold the employer liable.",
    elements: [
      {
        element: "Protected characteristic",
        description:
          "The harassment was based on a protected characteristic under FEHA (race, sex, gender, disability, age, religion, etc.).",
      },
      {
        element: "Unwelcome conduct",
        description:
          "The harassing conduct was unwelcome — you did not solicit or invite it, and you regarded it as undesirable or offensive.",
      },
      {
        element: "Severe or pervasive",
        description:
          "The conduct was sufficiently severe or pervasive to alter the conditions of employment and create a hostile, intimidating, or abusive work environment. A single incident can qualify if sufficiently severe (e.g., physical assault, use of a slur by a supervisor).",
      },
      {
        element: "Reasonable person standard",
        description:
          "A reasonable person in the plaintiff's position, considering all the circumstances, would find the environment hostile or abusive.",
      },
      {
        element: "Employer liability (for non-supervisor harassment)",
        description:
          "For harassment by co-workers or third parties, the employer knew or should have known about the harassment and failed to take immediate, appropriate corrective action. For supervisor harassment, the employer is strictly liable.",
      },
    ],
    deadlines: [
      {
        name: "CRD administrative complaint",
        period: "3 years",
        statute: "Gov. Code § 12960",
        notes:
          "From the last act of harassment. Continuing harassment may extend the deadline under the continuing violation doctrine.",
      },
      {
        name: "Right-to-sue lawsuit",
        period: "1 year",
        statute: "Gov. Code § 12965(c)(1)(C)",
        notes: "After receiving a right-to-sue notice from CRD.",
      },
    ],
    relevantStatutes: [
      "Gov. Code § 12940(j)",
      "Gov. Code § 12940(k)",
      "Gov. Code § 12960",
      "Gov. Code § 12950.1",
    ],
    primaryAgencies: ["CRD"],
    relatedClaimSlugs: [
      "feha-discrimination",
      "retaliation",
      "wrongful-termination",
    ],
    relatedTopicSlugs: [
      "discrimination-and-harassment",
      "retaliation-and-whistleblower",
    ],
    ctaQuery: "Ask About Your Harassment Claim",
    faqs: [
      {
        question:
          "What is the difference between hostile work environment and quid pro quo harassment?",
        answer:
          "Hostile work environment harassment involves unwelcome conduct based on a protected characteristic that is severe or pervasive enough to create an abusive working environment — such as repeated offensive jokes, slurs, or intimidating behavior. Quid pro quo harassment occurs when a supervisor or person in authority conditions employment benefits (hiring, promotion, continued employment) on the employee submitting to unwelcome conduct, typically sexual. A single quid pro quo incident is sufficient to state a claim.",
      },
      {
        question: "Can a single incident constitute harassment?",
        answer:
          "Yes. While hostile work environment claims often involve a pattern of conduct, a single incident can be sufficient if it is severe enough. California courts have found single incidents sufficient when they involve physical assault, use of a particularly egregious slur (especially by a supervisor), or quid pro quo demands. The more severe the individual incident, the less need to show a pattern of harassment.",
      },
      {
        question:
          "Can I hold my harasser personally liable under California law?",
        answer:
          "Yes. Under FEHA, individual harassers can be held personally liable for harassment — this is a significant difference from discrimination claims, where only the employer entity is liable. This means you can sue your harasser individually, and the harasser may be required to personally pay damages including compensatory damages for emotional distress and potentially punitive damages.",
      },
      {
        question:
          "What should I do if I am being harassed at work?",
        answer:
          "Document every incident with dates, times, witnesses, and details. Report the harassment to your supervisor, HR, or through your employer's complaint procedure — put it in writing. If your employer fails to act, file a complaint with the Civil Rights Department (CRD) within 3 years. Consult an employment attorney, especially if the harassment is ongoing. Do not delete any text messages, emails, or other evidence of harassment.",
      },
      {
        question:
          "Is my employer required to have a harassment prevention policy?",
        answer:
          "Yes. California law requires all employers to: distribute a written harassment prevention policy, provide sexual harassment prevention training (2 hours for supervisors, 1 hour for non-supervisory employees every 2 years), and display a poster on harassment and discrimination rights. Employers with 5 or more employees must provide this training. Failure to comply does not create a standalone claim but can support a harassment case by showing the employer failed to take reasonable steps to prevent harassment.",
      },
    ],
  },
  {
    slug: "wage-theft",
    title: "Wage Theft Claims in California",
    shortTitle: "Wage Theft",
    description:
      "California wage theft claims for unpaid wages, overtime violations, meal and rest break premiums, and pay stub violations.",
    metaDescription:
      "Are you a victim of wage theft in California? Learn about unpaid wages, overtime violations, meal break premiums, filing deadlines, and how to recover your money. Free AI guidance.",
    overview:
      "Wage theft — the failure to pay workers their legally owed compensation — is the most common employment law violation in California. It encompasses unpaid minimum wages, overtime violations, missed meal and rest break premiums, illegal deductions, failure to reimburse business expenses, and inaccurate pay stubs. The California Labor Code provides strong remedies including waiting time penalties (up to 30 days of wages), pay stub penalties, and interest. Wage claims can be filed with the Labor Commissioner (DLSE) without an attorney, or pursued through civil litigation or PAGA representative actions.",
    elements: [
      {
        element: "Employment relationship",
        description:
          "You were an employee (not a bona fide independent contractor) entitled to wage protections under the Labor Code.",
      },
      {
        element: "Wages owed",
        description:
          "Your employer failed to pay wages you earned — including minimum wage, overtime, meal/rest break premiums, commissions, bonuses, or vacation pay.",
      },
      {
        element: "Employer obligation",
        description:
          "The employer was legally required to make the payment (e.g., the overtime exemption did not apply, or a meal break was not provided).",
      },
      {
        element: "Amount unpaid",
        description:
          "You can calculate the specific amount of wages owed, including any applicable premiums, penalties, and interest.",
      },
    ],
    deadlines: [
      {
        name: "Unpaid wages (Labor Code)",
        period: "3 years",
        statute: "Code Civ. Proc. § 338(a)",
        notes: "For most Labor Code wage violations including overtime and minimum wage.",
      },
      {
        name: "Written contract wages",
        period: "4 years",
        statute: "Code Civ. Proc. § 337",
        notes:
          "If wages are owed under a written contract (e.g., commission agreement).",
      },
      {
        name: "UCL claim for wages",
        period: "4 years",
        statute: "Bus. & Prof. Code § 17208",
        notes: "An Unfair Competition Law claim can extend recovery period for restitution.",
      },
      {
        name: "PAGA penalties",
        period: "1 year",
        statute: "Lab. Code § 2699.3",
        notes: "For seeking civil penalties through a PAGA representative action.",
      },
    ],
    relevantStatutes: [
      "Lab. Code §§ 510, 1194 (overtime)",
      "Lab. Code §§ 226.7, 512 (meal/rest breaks)",
      "Lab. Code § 226 (pay stubs)",
      "Lab. Code § 203 (waiting time penalties)",
      "Lab. Code § 2802 (expense reimbursement)",
    ],
    primaryAgencies: ["DIR/DLSE"],
    relatedClaimSlugs: ["paga", "misclassification", "retaliation"],
    relatedTopicSlugs: [
      "wages-and-compensation",
      "complaint-and-claims-process",
      "unfair-business-practices",
    ],
    ctaQuery: "Ask About Your Unpaid Wages",
    faqs: [
      {
        question: "What counts as wage theft in California?",
        answer:
          "Wage theft includes: paying below minimum wage, not paying overtime (over 8 hours/day or 40 hours/week), denying meal breaks (30 min for 5+ hour shifts) or rest breaks (10 min per 4 hours), making illegal deductions from pay, not reimbursing required business expenses, misclassifying employees as exempt to avoid overtime, failing to pay commissions or bonuses earned, not providing accurate itemized pay stubs, and not paying all wages due upon termination.",
      },
      {
        question:
          "How do I file a wage claim with the Labor Commissioner?",
        answer:
          "File a wage claim (Berman hearing) with the DLSE online at dir.ca.gov, by mail, or in person at a local DLSE office. There is no filing fee, and you do not need an attorney. The DLSE will schedule a conference to try to resolve the claim, followed by a hearing before a deputy labor commissioner if needed. The process typically takes several months. You can claim unpaid wages going back 3 years.",
      },
      {
        question:
          "What penalties can my employer face for wage theft?",
        answer:
          "Penalties include: waiting time penalties of up to 30 days of daily wages if final pay is late (Lab. Code § 203), pay stub penalties of $50 for first violation and $100 per subsequent violation up to $4,000 (Lab. Code § 226), meal/rest break premiums of one additional hour of pay per violation per day, interest on unpaid wages, liquidated damages equal to the unpaid wages plus interest for minimum wage violations, and attorney's fees if you prevail in court.",
      },
      {
        question: "Can I recover wages if I was paid in cash or off the books?",
        answer:
          "Yes. California wage protections apply regardless of how you were paid. Even if you were paid in cash, worked 'off the books,' or lack documentation, you can still file a wage claim. The DLSE will consider all available evidence including your testimony, any records you kept, bank deposits, and witness statements. Being paid in cash does not make you an independent contractor — the work relationship determines your status.",
      },
      {
        question:
          "What is the difference between filing a wage claim and filing a lawsuit?",
        answer:
          "A DLSE wage claim (Berman hearing) is free, does not require an attorney, and is handled by the Labor Commissioner — but recovery is limited to your individual unpaid wages and penalties. A civil lawsuit allows broader claims and damages, can include a PAGA representative action on behalf of other workers, and may result in larger awards — but typically requires an attorney. Many workers start with the DLSE process. If you are owed a significant amount or other workers are affected, a lawsuit or PAGA claim may be more effective.",
      },
      {
        question: "Can my employer retaliate against me for filing a wage claim?",
        answer:
          "No. Labor Code § 98.6 prohibits employers from retaliating against employees for filing wage claims, testifying about wages, or exercising any rights under the Labor Code. If you are terminated or disciplined within 90 days of filing a wage complaint, there is a rebuttable presumption of retaliation. Remedies for retaliation include reinstatement, back pay, and a penalty of up to $10,000.",
      },
    ],
  },
  {
    slug: "retaliation",
    title: "Workplace Retaliation Claims in California",
    shortTitle: "Retaliation",
    description:
      "California retaliation claims for adverse actions after whistleblowing, filing complaints, or exercising workplace rights.",
    metaDescription:
      "Were you retaliated against at work in California? Learn about whistleblower protections, the 90-day presumption, filing deadlines, and how to prove retaliation. Free AI guidance.",
    overview:
      "California provides some of the strongest anti-retaliation protections in the nation. Multiple statutes prohibit employers from retaliating against employees who engage in protected activity — including reporting legal violations (whistleblowing under Lab. Code § 1102.5), filing wage claims, reporting safety hazards, requesting disability accommodations, taking protected leave, or filing discrimination complaints. A key feature of California law is the 90-day rebuttable presumption: if an adverse action occurs within 90 days of protected activity, retaliation is presumed.",
    elements: [
      {
        element: "Protected activity",
        description:
          "You engaged in a legally protected activity — such as reporting a legal violation, filing a complaint, requesting an accommodation, participating in an investigation, or exercising a workplace right.",
      },
      {
        element: "Adverse employment action",
        description:
          "Your employer took an adverse action against you — termination, demotion, suspension, reduction in hours/pay, negative performance review, reassignment to less desirable duties, or other materially adverse treatment.",
      },
      {
        element: "Causal connection",
        description:
          "There is a causal link between your protected activity and the adverse action. This can be shown through timing (especially within 90 days), direct statements, pattern of treatment, or deviation from standard procedures.",
      },
      {
        element: "Employer knowledge",
        description:
          "The decision-maker who took the adverse action knew about your protected activity.",
      },
    ],
    deadlines: [
      {
        name: "Lab. Code § 1102.5 whistleblower",
        period: "3 years",
        statute: "Code Civ. Proc. § 338(a)",
        notes: "For whistleblower retaliation claims under the Labor Code.",
      },
      {
        name: "FEHA retaliation",
        period: "3 years",
        statute: "Gov. Code § 12960",
        notes:
          "File with CRD within 3 years; then 1 year to file suit after receiving right-to-sue notice.",
      },
      {
        name: "Labor Commissioner complaint",
        period: "1 year",
        statute: "Lab. Code § 98.7",
        notes:
          "For filing a retaliation complaint with the Labor Commissioner (certain Labor Code retaliation claims).",
      },
    ],
    relevantStatutes: [
      "Lab. Code § 1102.5 (whistleblower)",
      "Lab. Code § 98.6 (wage complaint retaliation)",
      "Lab. Code § 6310 (safety complaint retaliation)",
      "Gov. Code § 12940(h) (FEHA retaliation)",
    ],
    primaryAgencies: ["CRD", "DIR"],
    relatedClaimSlugs: [
      "wrongful-termination",
      "feha-discrimination",
      "paga",
    ],
    relatedTopicSlugs: [
      "retaliation-and-whistleblower",
      "complaint-and-claims-process",
      "wages-and-compensation",
    ],
    ctaQuery: "Ask About Your Retaliation Claim",
    faqs: [
      {
        question:
          "What is the 90-day presumption in California retaliation cases?",
        answer:
          "Under several California statutes (including Lab. Code §§ 98.6 and 1102.5), if an employer takes an adverse action against an employee within 90 days of the employee engaging in protected activity, there is a rebuttable presumption that the action was retaliatory. This shifts the burden to the employer to prove a legitimate, non-retaliatory reason. While the employer can rebut this presumption, it is a powerful evidentiary tool for employees.",
      },
      {
        question: "What counts as protected activity under California law?",
        answer:
          "Protected activity includes: reporting suspected legal violations to a government agency or supervisor (whistleblowing), filing a wage claim or testifying about wages, reporting workplace safety hazards, filing a discrimination or harassment complaint, requesting disability or religious accommodations, taking CFRA or pregnancy disability leave, participating in an investigation or legal proceeding, and refusing to participate in illegal activity. You are protected even if the reported violation ultimately did not occur, as long as you had reasonable cause to believe it did.",
      },
      {
        question: "Can I prove retaliation without direct evidence?",
        answer:
          "Yes. Most retaliation cases rely on circumstantial evidence. Strong indicators include: close timing between your protected activity and the adverse action, your employer's departure from standard procedures, inconsistent or shifting explanations for the adverse action, similarly situated employees who did not engage in protected activity being treated better, increased scrutiny or negative performance reviews after protected activity, and evidence that the employer's stated reason is false (pretext).",
      },
      {
        question:
          "What remedies are available for workplace retaliation in California?",
        answer:
          "Remedies include: reinstatement to your former position, back pay with interest, compensation for lost benefits, compensatory damages for emotional distress, punitive damages (in cases of malice or oppression), attorney's fees and costs, and civil penalties. Under Lab. Code § 1102.5, employees may recover a civil penalty of up to $10,000 per violation. In some cases, the employer's officers and agents may be held personally liable.",
      },
      {
        question:
          "Where should I file a retaliation complaint — CRD, Labor Commissioner, or court?",
        answer:
          "It depends on the type of retaliation. For FEHA-related retaliation (discrimination, harassment, leave), file with CRD. For wage-related retaliation, file with the Labor Commissioner under Lab. Code § 98.6. For general whistleblower retaliation, you can file with the Labor Commissioner under § 1102.5 or go directly to court. You may also combine claims in a civil lawsuit. An employment attorney can help determine the best strategy for your specific situation.",
      },
    ],
  },
  {
    slug: "paga",
    title: "PAGA Claims in California",
    shortTitle: "PAGA Claims",
    description:
      "California Private Attorneys General Act (PAGA) representative actions for Labor Code violations and civil penalties.",
    metaDescription:
      "Learn about PAGA claims in California — the Private Attorneys General Act allows employees to seek civil penalties for Labor Code violations. Eligibility, process, and 75/25 split explained.",
    overview:
      "The Private Attorneys General Act (PAGA), codified in Labor Code §§ 2698–2699.8, allows an 'aggrieved employee' to step into the shoes of the state and enforce Labor Code violations on behalf of themselves and other current or former employees. PAGA is a powerful tool because it does not require class certification, cannot be fully waived by arbitration agreements for representative claims, and recovers civil penalties that would otherwise only be available to government agencies. Penalties are split 75% to the Labor and Workforce Development Agency (LWDA) and 25% to the aggrieved employees.",
    elements: [
      {
        element: "Aggrieved employee",
        description:
          "You are (or were) an employee who suffered at least one Labor Code violation alleged in the PAGA notice. You must have personally experienced the violation.",
      },
      {
        element: "Labor Code violation",
        description:
          "One or more violations of the California Labor Code occurred — such as unpaid overtime, missed meal/rest breaks, pay stub violations, or failure to pay minimum wage.",
      },
      {
        element: "LWDA notice",
        description:
          "You provided written notice to the Labor and Workforce Development Agency (LWDA) and to your employer identifying the specific Labor Code violations, at least 65 days before filing suit.",
      },
      {
        element: "65-day waiting period",
        description:
          "The LWDA did not cite the employer within the 65-day period, or the LWDA did not respond, allowing you to proceed with the PAGA action.",
      },
    ],
    deadlines: [
      {
        name: "PAGA statute of limitations",
        period: "1 year",
        statute: "Lab. Code § 2699.3(d)",
        notes:
          "From the date of the most recent Labor Code violation. The LWDA notice must be filed within this period.",
      },
      {
        name: "65-day waiting period",
        period: "65 calendar days",
        statute: "Lab. Code § 2699.3(a)(2)",
        notes: "After sending LWDA notice, wait 65 days before filing the PAGA lawsuit.",
      },
    ],
    relevantStatutes: [
      "Lab. Code §§ 2698–2699.8",
      "Lab. Code § 2699.3 (notice requirements)",
      "Lab. Code § 2699(a) (penalty amounts)",
    ],
    primaryAgencies: ["LWDA"],
    relatedClaimSlugs: ["wage-theft", "retaliation", "misclassification"],
    relatedTopicSlugs: [
      "unfair-business-practices",
      "wages-and-compensation",
      "complaint-and-claims-process",
    ],
    ctaQuery: "Ask About Filing a PAGA Claim",
    faqs: [
      {
        question: "What is a PAGA claim and how does it work?",
        answer:
          "PAGA allows an individual employee who has suffered a Labor Code violation to act as a 'private attorney general' and sue the employer for civil penalties on behalf of all aggrieved employees. Unlike a class action which seeks damages, PAGA seeks civil penalties — typically $100 per employee per pay period for the initial violation and $200 per employee per subsequent violation. 75% of any penalties recovered go to the LWDA (the state), and 25% go to the aggrieved employees.",
      },
      {
        question: "What is the LWDA notice requirement for PAGA?",
        answer:
          "Before filing a PAGA lawsuit, you must send written notice to the LWDA (online at dir.ca.gov/Private-Attorney-General-Act/PAGA.html) and to your employer. The notice must identify the specific Labor Code provisions violated and the facts supporting the violations. The LWDA then has 65 calendar days to decide whether to investigate. If the LWDA does not respond or declines to investigate, you may file the PAGA action in court.",
      },
      {
        question: "Can my employer force me to arbitrate my PAGA claim?",
        answer:
          "Following the U.S. Supreme Court's Viking River Cruises v. Moriana (2022) decision, an employer can compel arbitration of your individual PAGA claim if you signed an arbitration agreement. However, California courts (including the Adolph v. Uber Technologies (2023) decision) have held that even if your individual claim goes to arbitration, you retain standing to pursue the representative PAGA claim (on behalf of other employees) in court. The law in this area continues to evolve.",
      },
      {
        question:
          "How are PAGA penalties calculated?",
        answer:
          "The default PAGA civil penalty is $100 per aggrieved employee per pay period for the initial violation, and $200 per employee per pay period for each subsequent violation. If the underlying Labor Code section already provides a civil penalty, PAGA allows recovery of that statutory penalty instead. Courts have discretion to reduce penalties if the full amount would be unjust. In large cases with many employees and pay periods, PAGA penalties can reach millions of dollars.",
      },
      {
        question: "Do I need a lawyer for a PAGA claim?",
        answer:
          "While you are not legally required to have an attorney, PAGA claims are complex and virtually all successful PAGA actions are brought by attorneys. PAGA requires strict compliance with notice requirements, specific pleading of Labor Code violations, and management of representative claims. Most employment attorneys handle PAGA cases on contingency. Given the 1-year statute of limitations, consult an attorney promptly if you believe you have a PAGA claim.",
      },
    ],
  },
  {
    slug: "cfra-leave",
    title: "CFRA Family & Medical Leave Claims in California",
    shortTitle: "CFRA Leave Claims",
    description:
      "California Family Rights Act (CFRA) claims for denial of leave, interference, and retaliation for taking family or medical leave.",
    metaDescription:
      "Were you denied CFRA leave or punished for taking family leave in California? Learn about CFRA eligibility, employer obligations, and how to file a claim. Free AI guidance.",
    overview:
      "The California Family Rights Act (CFRA) provides eligible employees up to 12 weeks of job-protected, unpaid leave per year for family and medical reasons. CFRA claims arise when employers deny eligible leave requests, interfere with the right to take leave, or retaliate against employees for requesting or taking leave. CFRA is broader than federal FMLA in several ways — it covers employers with just 5 employees (FMLA requires 50), includes more family members (grandparents, grandchildren, siblings, domestic partners), and does not count pregnancy disability leave against the 12-week entitlement.",
    elements: [
      {
        element: "Eligible employee",
        description:
          "You worked for an employer with 5 or more employees, had at least 12 months of service, and worked at least 1,250 hours in the 12 months before leave.",
      },
      {
        element: "Qualifying reason",
        description:
          "Your leave was for a qualifying reason: your own serious health condition, caring for a family member with a serious health condition, bonding with a new child (birth, adoption, or foster care), or a qualifying military exigency.",
      },
      {
        element: "Interference or retaliation",
        description:
          "Your employer denied your leave request, discouraged you from taking leave, failed to reinstate you to the same or comparable position, or took adverse action because you requested or took CFRA leave.",
      },
      {
        element: "Damages",
        description:
          "You suffered harm as a result — lost wages, lost benefits, emotional distress, or other damages.",
      },
    ],
    deadlines: [
      {
        name: "CRD administrative complaint",
        period: "3 years",
        statute: "Gov. Code § 12960",
        notes:
          "From the date of the CFRA violation (denial, interference, or retaliation). CFRA is enforced through FEHA.",
      },
      {
        name: "Right-to-sue lawsuit",
        period: "1 year",
        statute: "Gov. Code § 12965(c)(1)(C)",
        notes: "After receiving a right-to-sue notice from CRD.",
      },
    ],
    relevantStatutes: [
      "Gov. Code §§ 12945.2, 12945.6 (CFRA)",
      "Gov. Code § 12940 (FEHA enforcement)",
      "Gov. Code § 12945 (pregnancy disability leave)",
      "29 U.S.C. § 2601+ (federal FMLA)",
    ],
    primaryAgencies: ["CRD"],
    relatedClaimSlugs: [
      "feha-discrimination",
      "retaliation",
      "wrongful-termination",
    ],
    relatedTopicSlugs: [
      "leave-and-time-off",
      "discrimination-and-harassment",
      "complaint-and-claims-process",
    ],
    ctaQuery: "Ask About Your CFRA Leave Rights",
    faqs: [
      {
        question: "Who is eligible for CFRA leave?",
        answer:
          "You are eligible if you: (1) work for an employer with 5 or more employees anywhere, (2) have worked for the employer for at least 12 months (need not be consecutive), and (3) have worked at least 1,250 hours in the 12 months before your leave starts. Unlike federal FMLA, CFRA has no requirement that you work at a site with 50+ employees within 75 miles, making it accessible to far more California workers.",
      },
      {
        question:
          "Can my employer fire me for taking CFRA leave?",
        answer:
          "No. CFRA makes it unlawful for an employer to retaliate against an employee for requesting, taking, or returning from CFRA leave. You are entitled to reinstatement to the same or a comparable position upon returning from leave. If you are terminated, demoted, or otherwise penalized for exercising your CFRA rights, you may file a complaint with CRD and/or a civil lawsuit seeking back pay, emotional distress damages, and attorney's fees.",
      },
      {
        question:
          "What is the difference between CFRA interference and CFRA retaliation?",
        answer:
          "Interference occurs when an employer prevents you from exercising your CFRA rights — denying a valid leave request, discouraging you from taking leave, failing to inform you of your rights, or refusing reinstatement. Interference does not require discriminatory intent. Retaliation occurs when an employer takes adverse action because you requested or took leave — such as firing, demotion, or poor reviews. Both are separate CFRA violations, and you can pursue both claims simultaneously.",
      },
      {
        question: "How is CFRA different from FMLA?",
        answer:
          "Key differences: CFRA covers employers with 5+ employees (FMLA requires 50+); CFRA includes domestic partners, grandparents, grandchildren, and siblings as qualifying family members (FMLA does not); CFRA leave for pregnancy disability is separate from the 12-week entitlement (under FMLA, pregnancy disability counts against the 12 weeks); and CFRA has no worksite-size requirement. In most situations, CFRA provides broader protections for California employees.",
      },
      {
        question: "Can I take CFRA leave intermittently?",
        answer:
          "Yes. If medically necessary for your own or a family member's serious health condition, you can take CFRA leave in increments — even as little as one hour at a time. For bonding with a new child, the minimum increment is two weeks, though an employer must grant at least two requests for leave of less than two weeks. Your employer cannot require you to transfer to an alternative position solely because you take intermittent leave.",
      },
    ],
  },
  {
    slug: "misclassification",
    title: "Worker Misclassification Claims in California",
    shortTitle: "Misclassification",
    description:
      "California worker misclassification claims under the ABC test (Dynamex/AB 5), independent contractor vs. employee status.",
    metaDescription:
      "Are you misclassified as an independent contractor in California? Learn about the ABC test, AB 5, the Dynamex decision, penalties, and how to recover lost wages and benefits.",
    overview:
      "Worker misclassification occurs when an employer improperly classifies an employee as an independent contractor to avoid paying wages, overtime, benefits, payroll taxes, and workers' compensation insurance. California applies the strict ABC test — established by the California Supreme Court in Dynamex Operations West v. Superior Court (2018) and codified by AB 5 — which presumes a worker is an employee unless the employer proves all three prongs: (A) the worker is free from the employer's control and direction, (B) the work is outside the employer's usual business, and (C) the worker has an independently established business. Willful misclassification carries penalties of $5,000 to $25,000 per violation.",
    elements: [
      {
        element: "Work performed",
        description:
          "You performed work or services for the employer (the hiring entity).",
      },
      {
        element: "Classified as independent contractor",
        description:
          "The employer classified you as an independent contractor rather than an employee, resulting in denial of employee protections (overtime, meal breaks, expense reimbursement, etc.).",
      },
      {
        element: "ABC test not satisfied",
        description:
          "The employer cannot prove all three prongs of the ABC test: (A) you were free from their control and direction in performing the work, (B) the work was outside the usual course of the employer's business, and (C) you were customarily engaged in an independently established trade, occupation, or business of the same nature.",
      },
      {
        element: "Damages from misclassification",
        description:
          "You were denied wages, overtime, meal/rest breaks, expense reimbursement, workers' compensation coverage, or other employee protections as a result of the misclassification.",
      },
    ],
    deadlines: [
      {
        name: "Unpaid wages",
        period: "3 years",
        statute: "Code Civ. Proc. § 338(a)",
        notes: "For recovering unpaid wages, overtime, and meal/rest break premiums.",
      },
      {
        name: "UCL claim",
        period: "4 years",
        statute: "Bus. & Prof. Code § 17208",
        notes:
          "An Unfair Competition Law claim extends the recovery period for restitution of unpaid wages.",
      },
      {
        name: "PAGA penalties",
        period: "1 year",
        statute: "Lab. Code § 2699.3(d)",
        notes: "For seeking civil penalties through a PAGA representative action.",
      },
    ],
    relevantStatutes: [
      "Lab. Code § 2775 (ABC test / AB 5)",
      "Lab. Code § 226.8 (willful misclassification penalties)",
      "Lab. Code §§ 510, 1194 (overtime)",
      "Bus. & Prof. Code § 17200 (UCL)",
    ],
    primaryAgencies: ["DIR/DLSE", "EDD"],
    relatedClaimSlugs: ["wage-theft", "paga", "retaliation"],
    relatedTopicSlugs: [
      "wages-and-compensation",
      "unfair-business-practices",
      "unemployment-benefits",
    ],
    ctaQuery: "Ask About Your Worker Misclassification Rights",
    faqs: [
      {
        question: "What is the ABC test for independent contractor status?",
        answer:
          "The ABC test (Lab. Code § 2775) presumes a worker is an employee. To classify you as an independent contractor, the employer must prove ALL three prongs: (A) you are free from the company's control and direction in performing the work, both under the contract and in fact; (B) you perform work that is outside the usual course of the company's business; and (C) you are customarily engaged in an independently established trade, occupation, or business of the same nature as the work you perform. If the employer fails any one prong, you are an employee.",
      },
      {
        question:
          "What rights am I losing if I am misclassified as an independent contractor?",
        answer:
          "Misclassification denies you: minimum wage and overtime pay, meal and rest break premiums, paid sick leave, workers' compensation insurance coverage, unemployment insurance benefits, employer-paid payroll taxes (Social Security, Medicare), expense reimbursement (Lab. Code § 2802), pay stub and recordkeeping protections, and protection under wage-and-hour laws. You also lose coverage under anti-discrimination, anti-retaliation, and workplace safety laws that protect employees.",
      },
      {
        question:
          "What penalties do employers face for misclassifying workers?",
        answer:
          "Under Lab. Code § 226.8, willful misclassification carries civil penalties of $5,000 to $15,000 per violation, and $10,000 to $25,000 for each subsequent violation or for a pattern or practice of violations. Employers may also face: unpaid wage liability plus interest, waiting time penalties, tax penalties from EDD and IRS, PAGA civil penalties, and a requirement to post a public notice of the violation. The Labor Commissioner, city attorneys, and affected workers can all bring enforcement actions.",
      },
      {
        question: "Are there exceptions to the ABC test?",
        answer:
          "Yes. AB 5 (Lab. Code §§ 2775–2787) and subsequent legislation (AB 2257) created exceptions for certain occupations that use the older, more flexible Borello multi-factor test instead. Exempted categories include: licensed professionals (doctors, lawyers, accountants, architects), certain creative professionals (fine artists, writers, photographers with specific conditions), real estate agents, commercial fishers, and certain business-to-business relationships meeting strict criteria. Even under Borello, misclassification is still possible.",
      },
      {
        question:
          "How do I file a misclassification complaint?",
        answer:
          "You have several options: (1) File a wage claim with the DLSE (Labor Commissioner) to recover unpaid wages — free, no attorney needed. (2) Report misclassification to EDD, which investigates payroll tax violations. (3) File a civil lawsuit for wages, penalties, and damages. (4) File a PAGA representative action for civil penalties on behalf of all affected workers. (5) Report to the city attorney in cities with local enforcement. Multiple options can be pursued simultaneously.",
      },
    ],
  },
];

/**
 * Get a claim by its slug.
 */
export function getClaimBySlug(slug: string): ClaimType | undefined {
  return claims.find((c) => c.slug === slug);
}

/**
 * Get all claim slugs for static generation.
 */
export function getAllClaimSlugs(): string[] {
  return claims.map((c) => c.slug);
}

/**
 * Get claims related to a given topic slug.
 */
export function getClaimsForTopic(topicSlug: string): ClaimType[] {
  return claims.filter((c) => c.relatedTopicSlugs.includes(topicSlug));
}
