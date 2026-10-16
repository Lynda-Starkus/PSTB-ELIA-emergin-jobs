"""Build small, reproducible evidence packs for the recorded ELIA walkthrough.

The HN matching is evaluated by Node with the exact TITLE_RULES from
tools/build_data.mjs. No archive, taxonomy, or existing browser bundle is changed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

NODE_AUDIT = r"""
const fs = require('fs'), vm = require('vm');
const source = fs.readFileSync('tools/build_data.mjs', 'utf8');
const match = source.match(/const TITLE_RULES = (\{[\s\S]*?\n\});/);
if (!match) throw new Error('TITLE_RULES could not be extracted');
const rules = vm.runInNewContext('(' + match[1] + ')');
const bundle = fs.readFileSync('data/data.js', 'utf8');
const bundleMatch = bundle.match(/window\.ELIA_DATA\s*=\s*(\{.*?\});(?:\r?\n|$)/s);
if (!bundleMatch) throw new Error('ELIA_DATA could not be extracted');
const data = JSON.parse(bundleMatch[1]);
const months = data.months;
const sums = Object.fromEntries(Object.keys(rules).map(id => [id, []]));
for (const month of months) {
  const texts = JSON.parse(fs.readFileSync('.cache/hn/' + month + '.json', 'utf8')).texts;
  for (const [id, regex] of Object.entries(rules)) {
    sums[id].push(texts.reduce((n, text) => n + Number(regex.test(text)), 0));
  }
}
const mining = fs.readFileSync('tools/mine_discovery.mjs', 'utf8');
const miningRules = mining.match(/const LEVEL_WORDS =[\s\S]*?(?=\nconst rows =)/);
if (!miningRules) throw new Error('Discovery title filter could not be extracted');
const filters = vm.runInNewContext(miningRules[0] + '\n({normalize, AI_LEX, AI_FALSE})');
const ftOffers = JSON.parse(fs.readFileSync('data/corpus_ft.json', 'utf8')).offers;
const lexicalOffers = ftOffers.filter(offer => {
  const normalized = filters.normalize(offer.t);
  return normalized && filters.AI_LEX.test(normalized) && !filters.AI_FALSE.test(normalized);
});
const contracts = {};
for (const offer of lexicalOffers) contracts[offer.c || 'unknown'] = (contracts[offer.c || 'unknown'] || 0) + 1;
const juniorWords = /\b(stage|stagiaire|alternance|alternant(?:e)?|apprenti(?:e)?|junior)\b/i;
const juniorOffers = lexicalOffers.filter(offer => juniorWords.test(offer.t))
  .sort((a,b) => String(b.d).localeCompare(String(a.d)) || String(a.id).localeCompare(String(b.id)));
const seenJuniorTitles = new Set();
const juniorExamples = [];
for (const offer of juniorOffers) {
  const normalizedTitle = offer.t.toLowerCase().trim();
  if (seenJuniorTitles.has(normalizedTitle)) continue;
  seenJuniorTitles.add(normalizedTitle);
  if (juniorExamples.length < 5) juniorExamples.push({id: offer.id, label: offer.t, date: offer.d, contract: offer.c});
}
process.stdout.write(JSON.stringify({months, counts: sums, meta: data.meta,
  ftLexicalAI: {count: lexicalOffers.length, contracts, juniorMatchCount: juniorOffers.length,
    juniorDistinctTitles: seenJuniorTitles.size, juniorExamples, examples: lexicalOffers.slice(0, 12).map(offer => offer.t)}}));
"""


def read_data(name: str) -> dict:
    return json.loads((ROOT / "data" / f"{name}.json").read_text(encoding="utf-8"))


def main() -> None:
    audit = json.loads(
        subprocess.run(
            ["node", "-e", NODE_AUDIT],
            cwd=ROOT,
            check=True,
            capture_output=True,
            encoding="utf-8",
        ).stdout
    )
    taxonomy = read_data("taxonomy")
    ft = read_data("ft_fr")
    discovery = read_data("discovery")
    regions = read_data("ft_regions")
    corpus = read_data("corpus_ft")
    adzuna = read_data("adzuna")
    months = audit["months"]
    families = {item["id"]: item for item in taxonomy["families"]}
    titles = {item["id"]: item for item in taxonomy["titles"]}
    current_window = {"from": months[-12], "to": months[-1]}
    previous_window = {"from": months[-24], "to": months[-13]}
    ft_day = ft["collected_at"][:10]
    hn_source = "Hacker News · archive internationale"
    ft_source = "France Travail · 4 octobre 2026"

    def title_item(title_id: str) -> dict:
        item = titles[title_id]
        counts = audit["counts"][title_id]
        previous = sum(counts[-24:-12])
        current = sum(counts[-12:])
        nonzero = [i for i, value in enumerate(counts) if value]
        result = ft["results"].get(title_id, {})
        return {
            "id": title_id,
            "label": item["title_fr"],
            "titleEn": item["title_en"],
            "category": item["category"],
            "family": item["family"],
            "previous": previous,
            "current": current,
            "hn24": previous + current,
            "growthPct": round((current - previous) / previous * 100, 1)
            if previous else None,
            "totalObserved": sum(counts),
            "firstObserved": months[nonzero[0]] if nonzero else None,
            "lastObserved": months[nonzero[-1]] if nonzero else None,
            "ftCount": result.get("count"),
            "ftRecent": result.get("count_31j"),
        }

    ai_titles = [
        title_item(item["id"])
        for item in taxonomy["titles"]
        if not families[item["family"]]["is_context"]
    ]
    bullish = sorted(
        (item for item in ai_titles if item["hn24"] >= 24
         and item["previous"] >= 8 and item["current"] > item["previous"]),
        key=lambda item: item["growthPct"],
        reverse=True,
    )[:5]
    bearish = sorted(
        (item for item in ai_titles if item["hn24"] >= 10
         and item["previous"] > 0 and item["current"] < item["previous"]),
        key=lambda item: item["growthPct"],
    )[:5]
    absent = sorted(
        (item for item in ai_titles if item["previous"] > 0 and item["current"] == 0),
        key=lambda item: (item["lastObserved"], item["id"]),
    )
    for item in bullish:
        if item["id"] == "mts":
            item["note"] = "Intitulé ancien ; sa hausse ne démontre pas un métier nouveau."
        if item["id"] == "prompt_engineer":
            item["note"] = "+100 % dans l’archive malgré le classement ELIA « en retrait »."
    for item in bearish:
        item["note"] = "Baisse de mentions ; faible effectif, aucun métier déclaré disparu."
    for item in absent:
        item["note"] = "Signal lexical absent sur douze mois après 1–2 mentions ; base trop faible pour conclure à une disparition."

    selected_ids = [
        "ai_engineer", "agent_engineer", "genai_engineer", "ai_automation_engineer", "fde"
    ]
    international_ids = [
        "fde", "ai_infrastructure_engineer", "inference_engineer", "mts", "prompt_engineer"
    ]
    international = [title_item(title_id) for title_id in international_ids]
    selected_france = []
    for title_id in selected_ids:
        item = title_item(title_id)
        item["source"] = ft_source
        item["queryCounts"] = ft["results"][title_id].get("terms", {})
        selected_france.append(item)

    candidates = []
    for rank, item in enumerate(discovery["fr"]["candidates"][:5], 1):
        candidates.append({
            "rank": rank,
            "label": item["label"],
            "count": item["count"],
            "variants": item["variants"],
            "score": item["score"],
            "sources": item["srcs"],
            "examples": item["examples"],
        })

    # Three rank positions, preserving the tie at third position.
    region_rows = sorted(regions["regions"], key=lambda item: item["total"], reverse=True)
    third_cutoff = region_rows[2]["total"]
    national_total = sum(item["total"] for item in region_rows)
    regional_top = []
    for item in region_rows:
        if item["total"] < third_cutoff:
            break
        rank = 1 + sum(other["total"] > item["total"] for other in region_rows)
        regional_top.append({
            "rank": rank,
            "code": item["code"],
            "label": item["nom"],
            "count": item["total"],
            "recent": item["recent"],
            "sharePct": round(item["total"] / national_total * 100, 1),
            "tied": sum(other["total"] == item["total"] for other in region_rows) > 1,
        })

    corpus_fields = sorted({key for offer in corpus["offers"] for key in offer})
    employer_rows = adzuna["companies"].get("ai_engineer", [])[:5]
    employer_ranking = []
    for item in employer_rows:
        employer_ranking.append({
            "rank": 1 + sum(other["count"] > item["count"] for other in employer_rows),
            "label": item["name"],
            "count": item["count"],
            "tied": sum(other["count"] == item["count"] for other in employer_rows) > 1,
        })
    lexical = audit["ftLexicalAI"]
    contract_rows = [
        {
            "code": code,
            "label": {"CDI": "CDI", "CDD": "CDD", "MIS": "Intérim", "LIB": "Profession libérale", "CCE": "Contrat d’engagement éducatif", "DDI": "Contrat à durée déterminée d’insertion", "SAI": "Saisonnier"}.get(code, code),
            "count": count,
            "sharePct": round(count / lexical["count"] * 100, 1),
        }
        for code, count in sorted(lexical["contracts"].items(), key=lambda row: row[1], reverse=True)
    ]
    outcomes = {
        "meta": {
            "frCollectedAt": ft["collected_at"],
            "frCollectedDate": ft_day,
            "hnSource": hn_source,
            "hnCurrentWindow": current_window,
            "hnPreviousWindow": previous_window,
            "hnArchiveWindow": {"from": months[0], "to": months[-1]},
            "hnAnalysed": audit["meta"]["analysed_total"],
            "frExtractTitles": discovery["fr"]["corpus_total"],
            "method": "Intitulés HN : regex exactes de tools/build_data.mjs, correspondances non exclusives, effectifs bruts par fenêtre de douze mois.",
        },
        "selectedFrance5": selected_france,
        "international5": international,
        "bullish5": bullish,
        "bearish5": bearish,
        "absent12Months": absent,
        "candidate5": candidates,
        "regionalTop3": regional_top,
        "labels": {
            "selectedFrance5": "Cinq rôles IA sélectionnés en France",
            "international5": "Cinq intitulés · mentions internationales et résultats France Travail",
            "bullish5": "Top 5 des intitulés IA en hausse · HN international",
            "bearish5": "Top 5 des intitulés IA en repli · HN international",
            "absent12Months": f"{len(absent)} signaux absents depuis douze mois · HN international",
            "candidate5": "Cinq groupes candidats · score exploratoire ELIA",
            "regionalTop3": "Trois premiers rangs régionaux · ex æquo au troisième",
        },
        "methods": {
            "selectedFrance5": "Sélection de rôles IA, pas un top 5 universel. Maximum des résultats des requêtes par alias ; chevauchements possibles.",
            "international5": "Mentions HN brutes sur douze mois et résultats de requêtes France Travail à la collecte. Deux sources et périmètres distincts ; ni mesure de retard français, ni croissance française.",
            "bullish5": "Familles IA hors contexte ; ≥24 mentions sur 24 mois et ≥8 dans la fenêtre précédente ; tri par variation des mentions.",
            "bearish5": "Familles IA hors contexte ; ≥10 mentions sur 24 mois, fenêtre précédente non nulle ; tri par variation des mentions. Faibles bases visibles.",
            "absent12Months": "Au moins une mention dans la fenêtre précédente, zéro dans la dernière. L’absence dans cette archive ne démontre pas la disparition d’un métier.",
            "candidate5": "Classement déjà calculé dans discovery.json. Regroupements lexicaux à valider ; « hors nomenclature » concerne le référentiel ELIA.",
            "regionalTop3": "France Travail, dix intitulés suivis, collecte du 4 octobre 2026. Résultats bruts par requêtes régionales ; trois rangs, quatre régions du fait d’un ex æquo.",
        },
        "optionalEvidence": {
            "ftCorpusCount": len(corpus["offers"]),
            "ftCorpusFields": corpus_fields,
            "employerRanking": {
                "available": True,
                "label": "Employeurs affichés pour la requête « AI engineer »",
                "source": "Adzuna France · 4 octobre 2026",
                "collectedAt": adzuna["collected_at"],
                "query": "AI engineer",
                "method": "Classement retourné par /top_companies?what=AI engineer ; résultats de cette requête, pas un top national ni des embauches réalisées.",
                "items": employer_ranking,
            },
            "ftContractMix": {
                "available": True,
                "label": "Contrats du sous-échantillon FT à intitulé lexical IA",
                "source": "France Travail · corpus rapatrié le 4 octobre 2026",
                "collectedAt": corpus["collected_at"],
                "denominator": lexical["count"],
                "ingestedCount": len(corpus["offers"]),
                "method": "Filtre lexical IA exact de mine_discovery.mjs après normalisation et exclusion des homonymes identifiés. Codes de contrat des offres observées ; sous-échantillon non représentatif, sélection lexicale à valider.",
                "items": contract_rows,
            },
            "juniorExamples": {
                "available": bool(lexical["juniorExamples"]),
                "label": "Exemples d’intitulés mentionnant stage, alternance ou junior",
                "source": "France Travail · sous-échantillon lexical IA · 4 octobre 2026",
                "collectedAt": corpus["collected_at"],
                "matchCount": lexical["juniorMatchCount"],
                "distinctTitles": lexical["juniorDistinctTitles"],
                "method": "Marqueur explicite stage/stagiaire/alternance/alternant/apprenti/junior dans le titre. Jusqu’à cinq titres distincts, triés par date. Exemples, pas classement national ni validation des conditions d’accès.",
                "items": lexical["juniorExamples"],
            },
            "juniorTop5": {"available": False, "reason": "Niveau d’expérience absent ; des mots dans le titre ne suffisent pas à classer les postes ouverts aux juniors."},
            "skillsTop5": {"available": False, "reason": "Descriptions et compétences absentes du corpus ; compétences de la taxonomie éditoriales, pas fréquences observées."},
            "migration": {"available": False, "reason": "Aucun suivi individuel ni comparaison des tâches pour établir une transition entre métiers."},
        },
        "limitations": [
            "La France est un instantané ; le momentum et les absences proviennent de l’archive internationale HN.",
            "Résultats de requêtes et mentions d’annonces, pas embauches réalisées ni budgets engagés.",
            "Un titre nouveau ne démontre pas un métier nouveau ; plusieurs intitulés retenus sont anciens.",
            "Les séries d’intitulés peuvent se chevaucher ; la sélection regex n’établit pas une représentativité nationale.",
            "Aucune liste étayée de cinq métiers rapidement disparus : seulement quatre signaux faibles sans mention sur la dernière fenêtre.",
        ],
    }
    target = ROOT / "data" / "outcomes.json"
    target.write_text(json.dumps(outcomes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {target.name}: {len(bullish)} bullish, {len(bearish)} bearish, {len(absent)} absent signals")


if __name__ == "__main__":
    main()
