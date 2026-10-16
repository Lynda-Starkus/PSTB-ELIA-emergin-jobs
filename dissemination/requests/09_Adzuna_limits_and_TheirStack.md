# Emails 9a and 9b — Adzuna (academic API key, higher limits) and TheirStack (France dataset quote)

## 9a — Adzuna: academic API key with higher limits

**To:** Adzuna API team, via the rate-limit contact form linked from the API terms (adzuna.co.uk/hire/partners/) and the licensing contact page (adzuna.co.uk/jobs/contact-us.html) · copy: info@adzuna.com
**Subject:** Academic API key with higher limits (14-day trial, then academic licence) — AI occupations in France (ELIA, PST&B / Université Gustave Eiffel)

Dear Adzuna API team,

I am a researcher at the ELIA laboratory (employment × AI) of Paris School of Technology & Business and at GRETTIA-COSYS, Université Gustave Eiffel. With Armand Derhy and Mahdi Zargayouna, we study how AI occupations emerge, spread and age in France from job postings (pre-registered lexical rules, Emergence Index per job title, LLM-judge validation).

Adzuna is one of the four sources of our open corpus (2.8 million postings), but our key (application ID: [app_id]) is limited to 250 calls/day, 1,000/week and 2,500/month, which prevents a monthly sweep of the French market. Could you grant:
1. an academic key with limits at least ten times higher for the 14-day evaluation period in your terms, to validate coverage, salary fields and descriptions for France (we receive the first 500 characters only);
2. then an academic licence for monthly French collection, ideally with full descriptions and your written consent to publish aggregated results?

In return: Adzuna credited as the source of all vacancy and salary data, as your terms require (paper, observatory, monthly barometer); a short co-authored note; early observatory access.

Data protection: no personal data collected; only aggregates published (counts below 10 suppressed); secure storage on university infrastructure; no redistribution of raw postings.

Kind regards,

Linda Belkessa
Researcher, ELIA laboratory — Paris School of Technology & Business, Paris 75011, France
GRETTIA-COSYS, Université Gustave Eiffel
linda.belkessa@univ-eiffel.fr · [phone]

**Attachments / notes**
- Optional attachment: `dissemination/onepager/onepager.pdf` (French; English summary on request).
- No developer-support address is published. The API terms (checked 15 October 2026) give default limits of 25 calls/minute, 250/day, 1,000/week and 2,500/month, point to the partners page for higher limits and to the contact page for licensing, and give info@adzuna.com for notices.
- The same terms grant commercial, government and academic users a 14-day trial "strictly for the purpose of validating the general coverage and quality of the data", after which "a licence agreement may be required"; they also require research to acknowledge Adzuna as the source of all salary and vacancy data, and bar trial data from being used "in its original format or in aggregation" without written consent, hence the request for written consent to publish aggregates.
- Give the application ID of the current key (ADZUNA_APP_ID in the project `.env`) in the form so that Adzuna can upgrade it; never paste the application key itself.

---

## 9b — TheirStack: quote for the France job postings dataset

**To:** TheirStack sales team, via the "Contact Sales" form (theirstack.com/en/contact)
**Subject:** Quote request — France job postings dataset since November 2022, academic use (ELIA, PST&B / Université Gustave Eiffel)

Dear TheirStack team,

I am a researcher at the ELIA laboratory (employment × AI) of Paris School of Technology & Business and at GRETTIA-COSYS, Université Gustave Eiffel. With Armand Derhy and Mahdi Zargayouna, we study how AI occupations emerge, spread and age in France from job postings (pre-registered lexical rules, Emergence Index per job title, LLM-judge validation).

Our open corpus (2.8 million postings) is dominated by France Travail and the public sector. We would like a quote, including any academic pricing, for:
1. your France job postings dataset from November 2022 to date (HelloWork, Indeed, LinkedIn, Welcome to the Jungle and ATS career pages), as one historical file (CSV or Parquet) plus monthly updates;
2. the fields title, full description, company, location, posting date, contract type, salary and source;
3. first, a sample extract of French postings to validate the schema.

We would need the right to publish aggregated results (peer-reviewed journal, public observatory). In return: TheirStack credited as data provider in our paper, observatory and monthly barometer; a co-authored note on AI hiring in France; early observatory access.

Data protection: no personal data (recruiter and contact fields excluded); only aggregates published (counts below 10 suppressed); secure storage on university infrastructure; no redistribution of raw postings.

Kind regards,

Linda Belkessa
Researcher, ELIA laboratory — Paris School of Technology & Business, Paris 75011, France
GRETTIA-COSYS, Université Gustave Eiffel
linda.belkessa@univ-eiffel.fr · [phone]

**Attachments / notes**
- Optional attachment: `dissemination/onepager/onepager.pdf` (French; English summary on request).
- Contact Sales is a web form: no sales address is published on theirstack.com. An address, hi@theirstack.com, appears only on a third-party company profile and is unverified; use it only if the form fails.
- Checked 15 October 2026: the France page shows monthly data from November 2022, with Indeed, LinkedIn and Welcome to the Jungle among the main sources and HelloWork and ATS career pages also covered; the datasets documentation describes delivery via S3 in CSV or Parquet, as a one-off historical download, daily updates, or both. No academic pricing is published, hence the explicit request.
