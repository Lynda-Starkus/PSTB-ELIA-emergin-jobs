# ELIA — Observatoire des métiers de l'IA

## Slide de cadrage CELIA → métiers émergents

Ouvrir `onepager.html` directement dans un navigateur : une page de cadrage sobre, polices et logo intégrés, lecture à 100 %. Tous les sujets sont visibles. `F` : plein écran ; `1`, `2`, `3` : indiquer le sujet discuté sans déplacer ni redimensionner le contenu ; `R` : rejouer le tracé discret ; `P` : imprimer. Les cibles de diffusion renvoient directement aux sources officielles.

`onepager.pdf` fournit la version statique 16:9 d'une page, `onepager.png` l'aperçu, et `notes-projet-superviseur.md` les propositions de recherche, le questionnaire et les cibles de diffusion sourcées. La source éditable est `tools/onepager.template.html`. Après une modification : `python tools/prepare_onepager.py`, puis `python tools/export_onepager.py` (Playwright, Chromium installé et pypdf). La préparation réintègre les polices et le logo depuis le cache, ou les télécharge si nécessaire.

Laboratoire ELIA (emploi × IA), PST&B — Paris School of Technology & Business.
Suivi des intitulés de postes créés par la vague IA dans les annonces d'emploi.
**Données réelles multi-sources** — aucune série synthétique.

## Sources actives

| Source | Rôle | Accès |
|---|---|---|
| Hacker News « Who is hiring » (API Algolia) | séries mensuelles 2011→2026 par famille et intitulé (Fig. 1, 2, sparklines) | ouvert |
| France Travail — API Offres d'emploi v2 | offres en ligne France par intitulé, total + ≤ 31 j (Fig. 3, colonne Offres FR) | clé `.env` |
| RemoteOK (API publique) | appoint : offres remote mondiales par intitulé | ouvert |
| ROME 4.0 (data.gouv.fr) | rattachement des intitulés de la taxonomie | ouvert |

Catalogue complet et statuts de vérification : `data/sources.json`.

## Chaîne de traitement

```sh
cp .env.example .env            # identifiants francetravail.io (jamais commités)
node tools/ingest_hn.mjs             # crawl des 184 fils mensuels → .cache/hn/ (rejouable)
node tools/ingest_francetravail.mjs  # comptages FR par intitulé → data/ft_fr.json
node tools/ingest_ft_regions.mjs     # 18 régions + CDI + employeurs FDE → data/ft_regions.json
node tools/ingest_ft_offers.mjs      # rapatriement massif d'offres FT → data/corpus_ft.json
node tools/ingest_mass_fr.mjs        # intitulés CSP (DGAFP) + BPCE → data/corpus_public.json
node tools/ingest_remoteok.mjs       # appoint remote → data/remoteok.json (échec toléré)
node tools/mine_discovery.mjs        # fouille : clustering Jaccard + score de sous-groupe
                                     #   + apparitions HN ≥ 2022 → data/discovery.json
node tools/build_data.mjs            # classification + assemblage → data/series.json, data/data.js
node tools/build.mjs                 # embarque sources/régions/géo/découverte + dist/artifact.html
```

**Fouille (scène 05)** : normalisation des intitulés (genre, niveaux, lieux) → filtre lexical IA →
regroupement par similarité de Jaccard ≥ 0,55 (union-find) → score de sous-groupe
`taille × (0,45 + part ≤ 31 j) × 0,18 si déjà en nomenclature` → candidats émergents, exemples bruts
à l'appui. Côté archive HN : détection de n-grammes de rôles apparus ≥ 2022 (≥ 8 mentions),
premier mois, vélocité 12 mois. LinkedIn n'a pas d'API d'offres ouverte : il reste cité comme
référence (Economic Graph) ; la masse légale France = France Travail + CSP + BPCE.

Classification **exclusive par priorité** (`tools/build_data.mjs`) : chaque annonce compte
dans sa première famille correspondante, familles IA testées avant les familles génériques,
pour des parts empilables sans double compte. Parts lissées sur 3 mois ; mois courant exclu.

## Structure

```
index.html         page observatoire (canonique, autonome)
data/taxonomy.json taxonomie : 4 états × 9 domaines × 10 niveaux, 23 familles, 58 intitulés
data/series.json   parts mensuelles réelles par famille (HN, lissées 3 mois)
data/data.js       bundle navigateur (window.ELIA_DATA + ELIA_SOURCES)
data/ft_fr.json    comptages France Travail par intitulé (horodatés)
assets/brand.json  tokens de marque ELIA/PST&B
tools/             ingestion + assemblage + build (voir ci-dessus)
```

## Feuille de route

- **v1.1** — couche européenne (CEDEFOP OJA, EURES), salaires Adzuna, actualisation planifiée.
- **v1.2** — détection automatique de nouveaux intitulés ; croisement avec l'indicateur CELIA.

## Visite guidée et vidéo

`index.html` reprend l'interface d'origine du commit `f99a007` : mêmes scènes, graphiques, cartes, polices, et passage du sombre au papier. Le bouton **Thème** permet de choisir **Original / Clair / Sombre**, avec préférence mémorisée. La **Visite guidée** de 3 min 09 ajoute des annotations courtes en haut à droite, titres de 34 px et texte de 26 px. Elle montre les résultats dans les graphiques et cartes d'origine, dont cinq rôles en France, cinq hausses, cinq reculs et quatre signaux absents. Espace : pause/reprise ; flèches : étape précédente/suivante ; Échap : fermer.

Le périmètre annoncé de l'étude est **+1 million d'offres en France** ; le corpus affiché contient **907 889 intitulés historiques et actuels**. Les comparaisons de momentum viennent de l'archive internationale Hacker News ; les volumes français sont des comptages bruts France Travail. Les annotations distinguent les sources et ne confondent pas annonces, embauches et dépenses des entreprises.

```powershell
python tools/video/build_outcomes.py
python tools/video/restore_native_ui.py
node tools/build.mjs
python tools/video/package_walkthrough.py
python tools/video/record_walkthrough.py --html deliverables/elia-scrollytelling.html --theme original --output deliverables/elia-visite-guidee-v3.mp4
```

`data/outcomes.json` conserve les chiffres, périodes, méthodes et limites des résultats affichés ; le script les reconstruit depuis les extraits locaux. Les absences HN concernent quatre intitulés à petits effectifs et ne prouvent pas la disparition des professions. Les candidats sont classés par score de découverte ; les volumes France Travail par requête peuvent se chevaucher. Les employeurs sont ceux affichés par Adzuna pour « AI engineer » ; les 337 contrats et les exemples juniors viennent d'un sous-échantillon lexical France Travail.

La restauration ajoute seulement les contrôles du thème et de la visite, ainsi que des points d'accès aux cartes pour sélectionner les résultats pendant la visite. Ses sources sont `tools/video/native_tour.css` et `tools/video/native_tour.js`. Fermer la visite rétablit les filtres du référentiel. Les styles et contenus visuels de la page d'origine restent dans le commit de référence.

`deliverables/elia-scrollytelling.html` embarque les données, D3 et les polices pour fonctionner hors ligne. Les sous-ensembles de polices conservent leurs plages Unicode ; l'encodage UTF-8 et les accents français sont vérifiés. `deliverables/elia-visite-guidee-v3.mp4` est l'enregistrement réel du navigateur en 1920 × 1080, avec annotations animées. Le script fournit aussi des sous-titres SRT, des aperçus et les métadonnées de vérification. La vidéo commence avec le thème d'origine puis montre le mode clair ; pour commencer en clair, utiliser `--theme light`. Les premières versions sont conservées dans `deliverables/previous/` et `deliverables/previous/v2/`.
