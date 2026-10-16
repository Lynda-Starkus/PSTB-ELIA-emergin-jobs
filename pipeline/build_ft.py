"""France Travail postings (HF parquet dumps + API NDJSON harvest) -> unified lake parquet."""
import sys, os, glob, json, hashlib, pandas as pd, pyarrow.parquet as pq
sys.stdout.reconfigure(encoding='utf-8')
root=sys.argv[1]; lake=os.path.join(root,'data-lake','lake'); os.makedirs(lake,exist_ok=True)
COLS=['id','intitule','description','dateCreation','dateActualisation','lieuTravail.libelle','lieuTravail.latitude','lieuTravail.longitude','lieuTravail.codePostal','lieuTravail.commune','romeCode','romeLibelle','appellationlibelle','entreprise.nom','typeContrat','natureContrat','experienceExige','experienceLibelle','salaire.libelle','dureeTravailLibelle','alternance','nombrePostes','qualificationCode','qualificationLibelle','codeNAF','secteurActivite','secteurActiviteLibelle','trancheEffectifEtab','origineOffre.origine','competences[].libelle','competences[].exigence','formations[].niveauLibelle','langues[].libelle','contexteTravail.conditionsExercice']
frames=[]
for f in sorted(glob.glob(os.path.join(root,'data-lake','raw','hf_ft','*.parquet'))):
    pf=pq.ParquetFile(f); cols=[c for c in COLS if c in pf.schema_arrow.names]
    df=pf.read(columns=cols).to_pandas(); df['ingest']='hf:'+os.path.basename(f); frames.append(df); print(os.path.basename(f),len(df))
def flat(r):
    g=lambda *k: (lambda d: [d:=d.get(x) if isinstance(d,dict) else None for x in k][-1])(r)
    o={'id':r.get('id'),'intitule':r.get('intitule'),'description':r.get('description'),'dateCreation':r.get('dateCreation'),'dateActualisation':r.get('dateActualisation'),
       'lieuTravail.libelle':g('lieuTravail','libelle'),'lieuTravail.latitude':g('lieuTravail','latitude'),'lieuTravail.longitude':g('lieuTravail','longitude'),'lieuTravail.codePostal':g('lieuTravail','codePostal'),'lieuTravail.commune':g('lieuTravail','commune'),
       'romeCode':r.get('romeCode'),'romeLibelle':r.get('romeLibelle'),'appellationlibelle':r.get('appellationlibelle'),'entreprise.nom':g('entreprise','nom'),'typeContrat':r.get('typeContrat'),'natureContrat':r.get('natureContrat'),
       'experienceExige':r.get('experienceExige'),'experienceLibelle':r.get('experienceLibelle'),'salaire.libelle':g('salaire','libelle'),'dureeTravailLibelle':r.get('dureeTravailLibelle'),'alternance':r.get('alternance'),'nombrePostes':r.get('nombrePostes'),
       'qualificationCode':r.get('qualificationCode'),'qualificationLibelle':r.get('qualificationLibelle'),'codeNAF':r.get('codeNAF'),'secteurActivite':r.get('secteurActivite'),'secteurActiviteLibelle':r.get('secteurActiviteLibelle'),'trancheEffectifEtab':r.get('trancheEffectifEtab'),'origineOffre.origine':g('origineOffre','origine'),
       'competences[].libelle':json.dumps([c.get('libelle') for c in (r.get('competences') or [])],ensure_ascii=False) if r.get('competences') else None,
       'competences[].exigence':json.dumps([c.get('exigence') for c in (r.get('competences') or [])],ensure_ascii=False) if r.get('competences') else None,
       'formations[].niveauLibelle':json.dumps([c.get('niveauLibelle') for c in (r.get('formations') or [])],ensure_ascii=False) if r.get('formations') else None,
       'langues[].libelle':json.dumps([c.get('libelle') for c in (r.get('langues') or [])],ensure_ascii=False) if r.get('langues') else None,
       'contexteTravail.conditionsExercice':json.dumps(g('contexteTravail','conditionsExercice'),ensure_ascii=False) if g('contexteTravail','conditionsExercice') else None}
    return o
rows=[]
for f in sorted(glob.glob(os.path.join(root,'data-lake','raw','ft_api','ft_*.ndjson'))):
    if not os.path.exists(f+'.done'): continue
    for line in open(f,encoding='utf-8'):
        line=line.strip()
        if not line: continue
        try: rows.append(flat(json.loads(line)))
        except Exception as e: pass
api=pd.DataFrame(rows); api['ingest']='api:2026-10-14'; print('api rows',len(api)); frames.append(api)
df=pd.concat(frames,ignore_index=True)
for c in ['lieuTravail.latitude','lieuTravail.longitude','nombrePostes']: df[c]=pd.to_numeric(df[c],errors='coerce')
df['origineOffre.origine']=df['origineOffre.origine'].astype(str)
before=len(df); df=df.sort_values('dateActualisation').drop_duplicates('id',keep='last'); print('dedup id',before,'->',len(df))
df['date_posted']=pd.to_datetime(df.dateCreation,errors='coerce',utc=True).dt.tz_localize(None)
df['month']=df.date_posted.dt.to_period('M').astype(str)
df['text']=(df.intitule.fillna('')+'\n'+df.description.fillna(''))
df['text_hash']=df.text.str.lower().str.replace(r'\s+',' ',regex=True).map(lambda s: hashlib.md5(s.encode('utf-8')).hexdigest())
df['dup_text']=df.duplicated('text_hash',keep='first')
df['dept']=df['lieuTravail.codePostal'].astype(str).str[:2]
df.loc[df['lieuTravail.codePostal'].astype(str).str.startswith('97'),'dept']=df['lieuTravail.codePostal'].astype(str).str[:3]
df['rome1']=df.romeCode.astype(str).str[:1]; df['rome3']=df.romeCode.astype(str).str[:3]
print(df.month.value_counts().sort_index().to_string())
print('dup_text share %.2f%%'%(100*df.dup_text.mean()))
df.to_parquet(os.path.join(lake,'ft_postings.parquet'),index=False); print('written',len(df))
