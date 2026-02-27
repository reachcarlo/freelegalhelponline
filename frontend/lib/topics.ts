/**
 * Topic definitions for SEO pages.
 * Based on Appendix A: California Employment Rights — Subject Matter Taxonomy.
 */

export interface TopicFAQ {
  question: string;
  answer: string;
}

export interface Topic {
  slug: string;
  title: string;
  shortTitle: string;
  description: string;
  metaDescription: string;
  overview: string;
  primaryAgencies: string[];
  primaryCodes: string[];
  relatedTopics: string[];
  faqs: TopicFAQ[];
}

export const topics: Topic[] = [
  {
    slug: "wages-and-compensation",
    title: "Wages & Compensation in California",
    shortTitle: "Wages & Compensation",
    description:
      "California wage laws covering minimum wage, overtime, meal and rest breaks, pay stubs, and final pay requirements.",
    metaDescription:
      "Learn about California wage laws — minimum wage rates, overtime rules, meal and rest break requirements, pay stub rights, and final pay deadlines. Free AI-powered guidance.",
    overview:
      "California has some of the strongest wage protections in the nation. The California Labor Code and the Industrial Welfare Commission (IWC) Wage Orders establish minimum wage rates, overtime requirements, meal and rest break rules, and strict requirements for pay stubs and final pay. The Division of Labor Standards Enforcement (DLSE) enforces these protections.",
    primaryAgencies: ["DIR/DLSE"],
    primaryCodes: ["Lab. Code Div. 2"],
    relatedTopics: [
      "employment-contracts",
      "complaint-and-claims-process",
      "unfair-business-practices",
    ],
    faqs: [
      {
        question: "What is the current minimum wage in California?",
        answer:
          "As of January 1, 2026, the California minimum wage is $16.90 per hour for all employers regardless of size. Some cities and counties have higher local minimum wages. Additionally, fast food restaurant workers have a minimum wage of $20.00 per hour, and healthcare workers have tiered minimum wages starting at $18.00–$23.00 per hour depending on facility type.",
      },
      {
        question:
          "When am I entitled to overtime pay in California?",
        answer:
          "Under California law, non-exempt employees are entitled to overtime pay at 1.5 times their regular rate for hours worked over 8 in a day or 40 in a week. Double time (2x regular rate) is required for hours over 12 in a day or over 8 on the seventh consecutive day of work. California's daily overtime threshold is more protective than federal law, which only requires weekly overtime.",
      },
      {
        question:
          "What are my rights to meal and rest breaks?",
        answer:
          "Non-exempt employees are entitled to a 30-minute unpaid meal break for shifts over 5 hours, and a second meal break for shifts over 10 hours. You are also entitled to a paid 10-minute rest break for every 4 hours worked. If your employer fails to provide these breaks, you are owed one additional hour of pay at your regular rate for each violation.",
      },
      {
        question:
          "What must be included on my pay stub?",
        answer:
          "California Labor Code § 226 requires detailed pay stubs showing: gross wages earned, total hours worked, piece rates (if applicable), all deductions, net wages, pay period dates, employee name and last four digits of SSN or employee ID, employer name and address, and all applicable hourly rates with hours at each rate. Violations can result in penalties of $50 for the first violation and $100 for subsequent violations.",
      },
      {
        question:
          "When must my employer pay me after I leave my job?",
        answer:
          "If you are fired or laid off, your employer must pay all wages owed immediately at the time of termination. If you quit with at least 72 hours notice, wages are due on your last day. If you quit without notice, wages are due within 72 hours. If your employer willfully fails to pay on time, you may be entitled to waiting time penalties of up to 30 days of wages under Labor Code § 203.",
      },
    ],
  },
  {
    slug: "discrimination-and-harassment",
    title: "Workplace Discrimination & Harassment in California",
    shortTitle: "Discrimination & Harassment",
    description:
      "California Fair Employment and Housing Act (FEHA) protections against workplace discrimination and harassment.",
    metaDescription:
      "Understand your rights under California's FEHA — protection from workplace discrimination and harassment based on race, gender, disability, age, and other categories. Free AI guidance.",
    overview:
      "The California Fair Employment and Housing Act (FEHA), codified in Government Code §§ 12900–12996, provides broad protections against employment discrimination and harassment. FEHA covers employers with 5 or more employees (harassment protections apply to all employers) and prohibits discrimination based on over 20 protected categories. The Civil Rights Department (CRD) enforces FEHA.",
    primaryAgencies: ["CRD"],
    primaryCodes: ["Gov. Code §§ 12900–12996"],
    relatedTopics: [
      "retaliation-and-whistleblower",
      "leave-and-time-off",
      "complaint-and-claims-process",
    ],
    faqs: [
      {
        question:
          "What categories are protected under California's FEHA?",
        answer:
          "FEHA protects against discrimination based on: race, color, national origin, ancestry, religion, sex (including pregnancy, childbirth, and related conditions), gender, gender identity, gender expression, sexual orientation, marital status, age (40+), disability (physical and mental), medical condition, genetic information, military/veteran status, and reproductive health decision-making. This is broader than federal Title VII protections.",
      },
      {
        question:
          "What counts as workplace harassment under California law?",
        answer:
          "Harassment includes unwelcome conduct based on a protected category that is severe or pervasive enough to create a hostile work environment, or quid pro quo harassment where employment benefits are conditioned on submitting to unwelcome conduct. A single incident can be sufficient if severe enough. California applies a reasonable person standard considering the totality of circumstances.",
      },
      {
        question:
          "Can my employer fire me because of my disability?",
        answer:
          "No. Under FEHA, employers must engage in a timely, good-faith interactive process to identify reasonable accommodations that allow you to perform your job's essential functions. Termination is only permitted if no reasonable accommodation exists or if accommodation would cause undue hardship. Failure to engage in the interactive process is itself a FEHA violation.",
      },
      {
        question:
          "How do I file a discrimination complaint in California?",
        answer:
          "You can file a complaint with the Civil Rights Department (CRD) within three years of the discriminatory act. You may also request an immediate right-to-sue notice from CRD without investigation. Once you receive a right-to-sue notice, you have one year to file a civil lawsuit. You can file online at calcivilrights.ca.gov or by mail.",
      },
      {
        question:
          "What damages can I recover in a discrimination case?",
        answer:
          "Available remedies include: back pay and lost benefits, front pay, compensatory damages for emotional distress, punitive damages (in cases of malice or reckless indifference), reasonable attorney's fees and costs, and injunctive relief. Unlike federal law, California does not cap compensatory or punitive damages in FEHA cases.",
      },
    ],
  },
  {
    slug: "retaliation-and-whistleblower",
    title: "Retaliation & Whistleblower Protections in California",
    shortTitle: "Retaliation & Whistleblower",
    description:
      "California protections for employees who report violations or exercise workplace rights.",
    metaDescription:
      "California retaliation and whistleblower protections — your rights when reporting violations, filing complaints, or exercising workplace rights. Free AI-powered legal guidance.",
    overview:
      "California provides extensive protections against employer retaliation. Labor Code § 1102.5 protects employees who report suspected legal violations. Additional protections cover employees who file workers' compensation claims, report safety hazards, exercise wage rights, or participate in union activities. Retaliation claims can be filed with the Labor Commissioner, CRD, or through a civil lawsuit.",
    primaryAgencies: ["CRD", "DIR"],
    primaryCodes: ["Lab. Code § 1102.5", "Gov. Code §§ 8547+"],
    relatedTopics: [
      "discrimination-and-harassment",
      "wages-and-compensation",
      "complaint-and-claims-process",
    ],
    faqs: [
      {
        question:
          "What is whistleblower retaliation under California law?",
        answer:
          "Under Labor Code § 1102.5, an employer may not retaliate against an employee for disclosing information to a government or law enforcement agency, or to a supervisor or other employee who has authority to investigate, if the employee has reasonable cause to believe the information discloses a violation of law. Retaliation includes termination, demotion, suspension, threats, or any adverse employment action.",
      },
      {
        question:
          "Can my employer fire me for filing a wage complaint?",
        answer:
          "No. California Labor Code § 98.6 prohibits employers from retaliating against employees who file wage claims, testify in proceedings, or exercise any rights under the Labor Code. If you are terminated within 90 days of engaging in protected activity, there is a rebuttable presumption of retaliation.",
      },
      {
        question:
          "What should I do if I believe I am being retaliated against?",
        answer:
          "Document everything — keep copies of any complaints you made, notes about changes in your treatment, and communications from your employer. File a complaint with the appropriate agency: the Labor Commissioner for wage-related retaliation, or CRD for FEHA-related retaliation. You may also consult an employment attorney about filing a civil lawsuit. Act promptly, as statute of limitations periods apply.",
      },
      {
        question:
          "What is the statute of limitations for a retaliation claim?",
        answer:
          "For Labor Code retaliation claims (such as § 1102.5 whistleblower retaliation), the statute of limitations is generally three years under Code of Civil Procedure § 338. For FEHA retaliation claims, you must file with CRD within three years. Some specific retaliation claims may have different deadlines, so prompt action is recommended.",
      },
      {
        question:
          "What remedies are available for retaliation?",
        answer:
          "Remedies for retaliation include: reinstatement, back pay with interest, compensation for lost benefits, compensatory damages for emotional distress, punitive damages, attorney's fees and costs, and civil penalties. Under Labor Code § 1102.5, employees may also recover a civil penalty of up to $10,000. In some cases, the employer's officers and agents may be held personally liable.",
      },
    ],
  },
  {
    slug: "leave-and-time-off",
    title: "Leave & Time Off Rights in California",
    shortTitle: "Leave & Time Off",
    description:
      "California leave laws including CFRA, pregnancy disability leave, paid family leave, sick leave, and SDI.",
    metaDescription:
      "California leave rights — CFRA family leave, pregnancy disability leave, paid family leave (PFL), sick leave, SDI, and bereavement leave. Free AI-powered guidance.",
    overview:
      "California provides extensive leave protections through multiple overlapping laws. The California Family Rights Act (CFRA) provides up to 12 weeks of job-protected leave. Pregnancy Disability Leave (PDL) provides up to four months. Paid Family Leave (PFL) and State Disability Insurance (SDI) provide partial wage replacement through EDD. California also mandates paid sick leave and bereavement leave.",
    primaryAgencies: ["CRD", "EDD"],
    primaryCodes: [
      "Gov. Code (FEHA/CFRA)",
      "Unemp. Ins. Code",
      "Lab. Code",
    ],
    relatedTopics: [
      "discrimination-and-harassment",
      "unemployment-benefits",
      "wages-and-compensation",
    ],
    faqs: [
      {
        question:
          "What is CFRA and who is eligible?",
        answer:
          "The California Family Rights Act (CFRA) provides eligible employees up to 12 weeks of unpaid, job-protected leave per year for: the birth or adoption/foster placement of a child, to care for a spouse, domestic partner, child, parent, grandparent, grandchild, or sibling with a serious health condition, or for the employee's own serious health condition. You are eligible if you work for an employer with 5+ employees, have worked there for 12+ months, and worked at least 1,250 hours in the past year.",
      },
      {
        question:
          "How much paid family leave can I get in California?",
        answer:
          "California Paid Family Leave (PFL) provides up to 8 weeks of partial wage replacement (approximately 60-70% of your weekly wages, up to a cap) when you need time off to care for a seriously ill family member or to bond with a new child. PFL is funded through employee payroll deductions and administered by EDD. PFL provides wage replacement but does not provide job protection — job protection comes from CFRA.",
      },
      {
        question:
          "What are my rights to paid sick leave in California?",
        answer:
          "Under California's Healthy Workplaces, Healthy Families Act, most employees earn at least 40 hours (5 days) of paid sick leave per year. You can use sick leave for your own health condition, to care for a family member, or if you are a victim of domestic violence, sexual assault, or stalking. Employers may not retaliate against you for using or requesting sick leave.",
      },
      {
        question:
          "Can I take leave for pregnancy in California?",
        answer:
          "Yes. Pregnancy Disability Leave (PDL) provides up to four months (17⅓ weeks) of job-protected leave for employees disabled by pregnancy, childbirth, or related conditions. PDL is available from employers with 5+ employees, with no minimum service requirement. After PDL, you may also be eligible for CFRA leave to bond with your newborn. During PDL, you may receive partial wage replacement through SDI.",
      },
      {
        question:
          "Am I entitled to bereavement leave in California?",
        answer:
          "Yes. Since January 1, 2023, California law requires employers with 5+ employees to provide up to 5 days of bereavement leave for the death of a spouse, child, parent, sibling, grandparent, grandchild, domestic partner, or parent-in-law. The leave need not be consecutive but must be completed within 3 months of the death. Bereavement leave is unpaid unless the employer's policy provides otherwise, but you may use accrued vacation or paid sick leave.",
      },
    ],
  },
  {
    slug: "workplace-safety",
    title: "Workplace Safety Rights in California",
    shortTitle: "Workplace Safety",
    description:
      "Cal/OSHA standards, hazard reporting rights, and workplace injury prevention in California.",
    metaDescription:
      "California workplace safety rights under Cal/OSHA — hazard reporting, safety standards, injury prevention, and protections against retaliation for safety complaints.",
    overview:
      "California's Division of Occupational Safety and Health (Cal/OSHA) enforces workplace safety standards that are often stricter than federal OSHA requirements. Employers must maintain a written Injury and Illness Prevention Program (IIPP), provide safety training, and comply with specific standards for their industry. Employees have the right to report hazards without retaliation.",
    primaryAgencies: ["DIR/Cal-OSHA"],
    primaryCodes: ["Lab. Code Div. 5", "Health & Saf. Code"],
    relatedTopics: [
      "retaliation-and-whistleblower",
      "workers-compensation",
    ],
    faqs: [
      {
        question:
          "How do I report an unsafe workplace in California?",
        answer:
          "You can file a complaint with Cal/OSHA by phone, mail, or online at dir.ca.gov. You can request that your identity be kept confidential. Cal/OSHA is required to investigate complaints and can conduct workplace inspections. You also have the right to refuse work that poses an imminent danger of death or serious harm, though you should report the hazard and give your employer a chance to correct it.",
      },
      {
        question:
          "Can my employer fire me for reporting a safety hazard?",
        answer:
          "No. California Labor Code § 6310 protects employees from retaliation for reporting safety or health violations, filing a safety complaint, or participating in a Cal/OSHA investigation. If you are retaliated against, you can file a complaint with the Labor Commissioner within one year, or file a civil lawsuit.",
      },
      {
        question:
          "What is an Injury and Illness Prevention Program (IIPP)?",
        answer:
          "Every California employer is required to have a written IIPP under Labor Code § 6401.7. The program must include: management commitment, a system for employee communication about safety, procedures for identifying and evaluating hazards, methods for correcting hazards, safety training, and recordkeeping. Failure to maintain an IIPP can result in Cal/OSHA citations and penalties.",
      },
      {
        question:
          "What are my rights if I am injured at work?",
        answer:
          "If you are injured at work, your employer must provide a workers' compensation claim form within one day of learning of the injury. You are entitled to medical treatment, temporary disability benefits, permanent disability benefits if applicable, and vocational rehabilitation. Your employer cannot require you to use your own health insurance for a work injury.",
      },
      {
        question:
          "Can I refuse to work in dangerous conditions?",
        answer:
          "California law allows you to refuse work that you reasonably believe poses a real and apparent hazard of death or serious injury. However, you should first report the hazard to your employer and to Cal/OSHA. If you refuse work, document your safety concerns in writing. Your employer cannot retaliate against you for good-faith safety complaints.",
      },
    ],
  },
  {
    slug: "workers-compensation",
    title: "Workers' Compensation in California",
    shortTitle: "Workers' Compensation",
    description:
      "California workers' compensation benefits, claims process, and employer obligations.",
    metaDescription:
      "California workers' compensation guide — benefits, claims process, medical treatment rights, and employer obligations for workplace injuries. Free AI-powered guidance.",
    overview:
      "California's workers' compensation system provides benefits to employees who are injured or become ill due to their job. Nearly all California employers must carry workers' compensation insurance. The system is no-fault — employees receive benefits regardless of who caused the injury. The Division of Workers' Compensation (DWC) oversees the system.",
    primaryAgencies: ["DIR/DWC"],
    primaryCodes: ["Lab. Code Div. 4"],
    relatedTopics: ["workplace-safety", "leave-and-time-off"],
    faqs: [
      {
        question:
          "What benefits does workers' compensation provide?",
        answer:
          "Workers' compensation provides: medical treatment for your injury or illness (no copay or deductible), temporary disability benefits (about two-thirds of your wages while you recover), permanent disability benefits if you don't fully recover, supplemental job displacement benefits (vouchers for retraining if you can't return to your job), and death benefits for dependents of workers killed on the job.",
      },
      {
        question: "How do I file a workers' compensation claim?",
        answer:
          "Report your injury to your employer as soon as possible. Your employer must give you a claim form (DWC-1) within one working day. Complete and return the form to your employer. Your employer then has one day to forward the claim to their insurance company, which must authorize up to $10,000 in medical treatment within one day of receiving the claim. The insurer has 90 days to accept or deny the claim.",
      },
      {
        question:
          "Can I choose my own doctor for a workers' comp injury?",
        answer:
          "You may predesignate your personal physician before an injury occurs by notifying your employer in writing. If you have not predesignated, you may be treated by a doctor in your employer's Medical Provider Network (MPN) for the first 30 days. After 30 days, you can switch to a doctor of your choice. If your employer does not have an MPN, you may choose your own doctor after the first 30 days.",
      },
      {
        question:
          "Can my employer fire me for filing a workers' comp claim?",
        answer:
          "No. Labor Code § 132a makes it a misdemeanor for an employer to discriminate against an employee for filing or intending to file a workers' compensation claim. If you are terminated, you may be entitled to reinstatement, back pay, increased compensation, and costs and expenses up to $10,000.",
      },
      {
        question:
          "What if my workers' comp claim is denied?",
        answer:
          "If your claim is denied, you have the right to request a hearing before a Workers' Compensation Administrative Law Judge (WCALJ). You should consult a workers' compensation attorney, as they work on contingency (no upfront fees). You can also contact the DWC Information and Assistance Unit for free help understanding your rights and the dispute process.",
      },
    ],
  },
  {
    slug: "unemployment-benefits",
    title: "Unemployment Benefits in California",
    shortTitle: "Unemployment Benefits",
    description:
      "California unemployment insurance eligibility, claims process, and employer obligations.",
    metaDescription:
      "California unemployment insurance guide — UI eligibility requirements, how to file a claim, weekly benefits, and what to do if your claim is denied. Free AI guidance.",
    overview:
      "California's Unemployment Insurance (UI) program provides temporary partial wage replacement to workers who lose their jobs through no fault of their own. The program is administered by the Employment Development Department (EDD) and funded by employer payroll taxes. Benefits typically last up to 26 weeks and are calculated based on your earnings during a base period.",
    primaryAgencies: ["EDD"],
    primaryCodes: ["Unemp. Ins. Code Div. 1"],
    relatedTopics: [
      "leave-and-time-off",
      "wages-and-compensation",
    ],
    faqs: [
      {
        question:
          "Am I eligible for unemployment benefits in California?",
        answer:
          "You may be eligible if you: lost your job through no fault of your own (layoff, reduction in force, etc.), earned enough wages during the base period (typically $1,300 in the highest-earning quarter or $900 in the highest quarter with total base period earnings of at least 1.25 times the highest quarter), are physically able and available to work, and are actively searching for work.",
      },
      {
        question: "How much will I receive in unemployment benefits?",
        answer:
          "Your weekly benefit amount is approximately 60-70% of your weekly wages during the highest-earning quarter of your base period, up to a maximum of $450 per week (this amount is adjusted periodically). The base period is typically the 12 months ending about 5 months before your claim start date. An alternate base period using more recent wages may be used if it gives you a higher benefit.",
      },
      {
        question: "Can I get unemployment if I quit my job?",
        answer:
          "Generally, you are not eligible for UI benefits if you voluntarily quit. However, you may still qualify if you quit for 'good cause,' which includes: unsafe working conditions, discrimination or harassment, a significant reduction in hours or pay, or health reasons that prevent you from working. You will need to provide evidence supporting your reason for quitting.",
      },
      {
        question:
          "What should I do if my unemployment claim is denied?",
        answer:
          "If your claim is denied, you have 30 days from the date on the denial notice to file an appeal with the California Unemployment Insurance Appeals Board (CUIAB). You will have a hearing before an Administrative Law Judge where you can present evidence and testimony. If the ALJ denies your appeal, you can further appeal to the CUIAB full board.",
      },
      {
        question:
          "Can I work part-time and still receive unemployment?",
        answer:
          "Yes. If you work part-time, you must report your gross earnings for each week you certify. EDD will reduce your weekly benefit amount by your earnings, but you may still receive partial benefits. You can earn up to 25% of your weekly benefit amount without any reduction. Earnings above that threshold reduce your benefits dollar-for-dollar.",
      },
    ],
  },
  {
    slug: "employment-contracts",
    title: "Employment Contracts & Non-Competes in California",
    shortTitle: "Employment Contracts",
    description:
      "California employment contract law including the ban on non-compete agreements, trade secrets, and at-will employment.",
    metaDescription:
      "California employment contract rights — non-compete agreements are void, trade secret rules, invention assignment limits, and at-will employment doctrine. Free AI guidance.",
    overview:
      "California has strong employee-protective contract laws. Non-compete agreements are generally void under Business & Professions Code § 16600, making California unique among states. The state also limits employer claims to employee inventions and protects employee mobility. Most employment in California is 'at-will,' meaning either party can end the relationship at any time for any lawful reason.",
    primaryAgencies: [],
    primaryCodes: ["Lab. Code Div. 3", "Bus. & Prof. Code § 16600+"],
    relatedTopics: [
      "wages-and-compensation",
      "unfair-business-practices",
    ],
    faqs: [
      {
        question:
          "Are non-compete agreements enforceable in California?",
        answer:
          "No. Under Business & Professions Code § 16600, non-compete agreements are void and unenforceable in California, with very limited exceptions for the sale of a business. As of January 1, 2024, employers are prohibited from even requiring employees to sign non-competes, and must notify current and former employees that any existing non-compete clauses are void. Violation can result in a lawsuit for injunctive relief and attorney's fees.",
      },
      {
        question: "What does at-will employment mean in California?",
        answer:
          "At-will employment means either the employer or employee can end the employment relationship at any time, for any lawful reason, with or without cause or advance notice. However, at-will employment does not allow termination for an illegal reason (discrimination, retaliation, etc.). An implied contract limiting at-will termination may be created through employer policies, handbooks, or oral promises.",
      },
      {
        question:
          "Does my employer own inventions I create on my own time?",
        answer:
          "Under Labor Code § 2870, employers cannot claim ownership of inventions you develop entirely on your own time, without using the employer's equipment, supplies, or trade secrets, unless the invention relates to the employer's business or results from work performed for the employer. Any employment agreement requiring you to assign such inventions is unenforceable to that extent.",
      },
      {
        question:
          "Can my employer require me to sign an arbitration agreement?",
        answer:
          "California has attempted to ban mandatory employment arbitration agreements (AB 51, Labor Code § 432.6), but federal courts have largely blocked enforcement of this law under the Federal Arbitration Act. As a practical matter, most employers can still require arbitration as a condition of employment. However, the arbitration agreement must be procedurally and substantively conscionable to be enforceable.",
      },
      {
        question:
          "What is a trade secret and what are the limits on NDAs?",
        answer:
          "Trade secrets are information deriving independent economic value from not being generally known, and which the owner takes reasonable steps to keep secret. Employers can require NDAs to protect legitimate trade secrets. However, NDAs cannot be used to prevent employees from disclosing information about unlawful acts in the workplace, including harassment and discrimination, under California's Silenced No More Act (SB 331).",
      },
    ],
  },
  {
    slug: "public-sector-employment",
    title: "Public Sector Employment in California",
    shortTitle: "Public Sector Employment",
    description:
      "Rights of California state and local government employees including civil service protections and collective bargaining.",
    metaDescription:
      "California public sector employment rights — civil service protections, collective bargaining, merit system, and PERB process for government employees.",
    overview:
      "California public sector employees enjoy additional protections beyond those available to private sector workers, including civil service and merit system protections, due process rights before disciplinary action, and collective bargaining rights administered by the Public Employment Relations Board (PERB). CalHR administers the state's human resources system.",
    primaryAgencies: ["CalHR", "PERB"],
    primaryCodes: ["Gov. Code Title 2 Div. 5"],
    relatedTopics: [
      "discrimination-and-harassment",
      "retaliation-and-whistleblower",
    ],
    faqs: [
      {
        question:
          "What civil service protections do California state employees have?",
        answer:
          "California civil service employees have a property interest in their employment, meaning they cannot be dismissed without due process. This typically includes notice of proposed action, a statement of reasons, the right to respond (Skelly hearing), and the right to appeal to the State Personnel Board. These protections do not apply during a probationary period.",
      },
      {
        question:
          "What is the role of PERB in California?",
        answer:
          "The Public Employment Relations Board (PERB) administers collective bargaining for California's public employees. PERB investigates unfair practice charges, conducts representation elections, and mediates disputes. If your employer or union commits an unfair practice (such as retaliating for union activity), you can file a charge with PERB within six months.",
      },
      {
        question:
          "Can public employees go on strike in California?",
        answer:
          "California law does not expressly prohibit public employee strikes, but courts have held that strikes may be enjoined if they create a substantial and imminent threat to public health or safety. Some categories of workers (such as firefighters and law enforcement) have binding arbitration provisions instead of the right to strike.",
      },
      {
        question:
          "What retirement benefits are California public employees entitled to?",
        answer:
          "Most California public employees participate in CalPERS (state and many local employees) or CalSTRS (teachers). These defined-benefit pension systems provide retirement benefits based on years of service, age at retirement, and final compensation. Vesting typically occurs after 5 years. The Public Employees' Pension Reform Act of 2013 (PEPRA) established lower benefit formulas for employees hired after January 1, 2013.",
      },
      {
        question:
          "Are whistleblower protections different for public employees?",
        answer:
          "Yes. In addition to the general protections under Labor Code § 1102.5, California government employees have additional protections under Government Code §§ 8547–8547.12 (the California Whistleblower Protection Act). State employees can report improper government activities to the State Auditor, and the law provides stronger protections and remedies specific to the public sector.",
      },
    ],
  },
  {
    slug: "unfair-business-practices",
    title: "Unfair Business Practices & PAGA in California",
    shortTitle: "Unfair Business Practices",
    description:
      "California UCL claims for employment violations and the Private Attorneys General Act (PAGA).",
    metaDescription:
      "California unfair business practices in employment — UCL claims, PAGA representative actions, and enforcement of labor law through private litigation.",
    overview:
      "California's Unfair Competition Law (UCL, Business & Professions Code § 17200+) provides a broad remedy for any unlawful, unfair, or fraudulent business practice — including employment law violations. The Private Attorneys General Act (PAGA, Labor Code § 2698+) allows employees to bring representative actions to enforce Labor Code violations on behalf of themselves and other aggrieved employees, recovering civil penalties that would otherwise be sought by government agencies.",
    primaryAgencies: [],
    primaryCodes: ["Bus. & Prof. Code § 17200+", "Lab. Code § 2698+"],
    relatedTopics: [
      "wages-and-compensation",
      "complaint-and-claims-process",
    ],
    faqs: [
      {
        question: "What is a PAGA claim?",
        answer:
          "A PAGA (Private Attorneys General Act) claim allows an aggrieved employee to act as a private attorney general to enforce Labor Code violations. Unlike a class action, PAGA claims seek civil penalties (not damages) on behalf of all aggrieved employees. 75% of PAGA penalties go to the Labor and Workforce Development Agency, and 25% go to the aggrieved employees. PAGA claims cannot be waived through arbitration agreements for representative claims.",
      },
      {
        question:
          "What do I need to do before filing a PAGA claim?",
        answer:
          "Before filing a PAGA lawsuit, you must give written notice to the Labor and Workforce Development Agency (LWDA) and to your employer, describing the specific Labor Code violations. The LWDA has 65 days to decide whether to investigate. If the LWDA does not respond or declines to investigate, you may proceed with the PAGA action in court.",
      },
      {
        question:
          "What is California's Unfair Competition Law (UCL)?",
        answer:
          "The UCL (Business & Professions Code § 17200) prohibits any unlawful, unfair, or fraudulent business act or practice. In the employment context, any violation of the Labor Code can form the basis for a UCL claim. UCL remedies include restitution and injunctive relief, but not damages or penalties. The statute of limitations is four years, which is longer than many underlying Labor Code claims.",
      },
      {
        question:
          "What is the difference between a PAGA claim and a class action?",
        answer:
          "Key differences: (1) PAGA seeks civil penalties, not individual damages; (2) PAGA does not require class certification; (3) PAGA penalties are shared 75/25 between the state and employees; (4) A PAGA judgment binds all aggrieved employees; (5) The U.S. Supreme Court held in Viking River that individual PAGA claims can be compelled to arbitration, but California courts continue to develop the law regarding representative PAGA claims.",
      },
      {
        question:
          "Can I bring a UCL claim for wage violations?",
        answer:
          "Yes. Any violation of the Labor Code qualifies as an 'unlawful' business practice under the UCL. This is particularly useful because the UCL has a four-year statute of limitations, which may allow recovery for violations that are time-barred under the Labor Code's shorter limitations periods. However, UCL remedies are limited to restitution (returning wages owed) and injunctive relief.",
      },
    ],
  },
  {
    slug: "complaint-and-claims-process",
    title: "Filing Complaints & Claims in California",
    shortTitle: "Complaints & Claims",
    description:
      "How to file employment complaints with California agencies, statutes of limitations, and the right-to-sue process.",
    metaDescription:
      "Guide to filing California employment complaints — agency procedures, statutes of limitations, administrative remedies, and the right-to-sue process. Free AI guidance.",
    overview:
      "California provides multiple avenues for enforcing employment rights. Depending on the violation, you may file complaints with the Civil Rights Department (CRD), the Labor Commissioner (DLSE), Cal/OSHA, or other agencies. Understanding statutes of limitations and exhaustion requirements is critical — some claims require filing an administrative complaint before you can sue in court.",
    primaryAgencies: ["CRD", "DIR", "PERB"],
    primaryCodes: ["Code Civ. Proc. § 340+", "Gov. Code"],
    relatedTopics: [
      "discrimination-and-harassment",
      "wages-and-compensation",
      "retaliation-and-whistleblower",
    ],
    faqs: [
      {
        question:
          "What are the statutes of limitations for employment claims in California?",
        answer:
          "Key deadlines: FEHA discrimination/harassment — 3 years to file with CRD; wage claims — 3 years for most Labor Code violations (Code Civ. Proc. § 338), 4 years under UCL; wrongful termination — 2 years (Code Civ. Proc. § 335.1); PAGA — 1 year; workers' comp — 1 year from injury; Cal/OSHA retaliation — 1 year. Once you receive a right-to-sue notice from CRD, you have 1 year to file suit.",
      },
      {
        question:
          "How do I file a wage claim with the Labor Commissioner?",
        answer:
          "You can file a wage claim (also called a Berman hearing claim) with the Division of Labor Standards Enforcement (DLSE) online, by mail, or in person. There is no filing fee. The DLSE will investigate and schedule a conference, followed by a hearing if necessary. An attorney is not required. Claims must generally be filed within 3 years of the violation.",
      },
      {
        question:
          "Do I need to file with an agency before suing in court?",
        answer:
          "It depends on the type of claim. FEHA claims require filing with CRD first (or requesting an immediate right-to-sue notice). Wage claims can go directly to court or through the DLSE. Workers' compensation claims must go through the workers' comp system. Labor Code retaliation claims generally do not require administrative exhaustion before filing suit.",
      },
      {
        question:
          "What is a right-to-sue notice?",
        answer:
          "A right-to-sue notice is a document issued by the Civil Rights Department (CRD) that authorizes you to file a FEHA lawsuit in court. You can request an immediate right-to-sue notice at any time, or CRD will issue one after investigation. Once you receive the notice, you have one year to file a civil lawsuit. Without a right-to-sue notice, you generally cannot bring a FEHA claim in court.",
      },
      {
        question:
          "Can I file multiple complaints with different agencies?",
        answer:
          "Yes, but be careful about overlapping claims and deadlines. For example, a discriminatory termination might give rise to a FEHA claim (CRD), a wrongful termination claim (court), and a PAGA claim (LWDA). Each has its own filing requirements and deadlines. An employment attorney can help coordinate multiple claims to maximize your recovery and avoid procedural pitfalls.",
      },
    ],
  },
];

/**
 * Get a topic by its slug.
 */
export function getTopicBySlug(slug: string): Topic | undefined {
  return topics.find((t) => t.slug === slug);
}

/**
 * Get all topic slugs for static generation.
 */
export function getAllTopicSlugs(): string[] {
  return topics.map((t) => t.slug);
}
