"""CSP (Choisir le Service Public) archives -> unified parquet (titles + metadata, no description)."""
import sys, os, glob, pandas as pd, hashlib
sys.stdout.reconfigure(encoding='utf-8')
root=sys.argv[1]; src=os.path.join(root,'data-lake','raw','csp'); dst=os.path.join(root,'data-lake','lake','csp_postings.parquet')
os.makedirs(os.path.dirname(dst),exist_ok=True)
cols={'Organisme de rattachement':'organisme','Référence':'ref','Versant':'versant','Métier':'metier_rmfp','Statut du poste':'statut','Nature de l\'emploi':'nature_emploi','Intitulé du poste':'title','Localisation du poste':'localisation','Lieu d\'affectation':'lieu','Niveau d\'études':'niveau_etudes','Niveau d\'expérience min. requis':'experience','Date de première publication':'date_first_pub','Date de début de publication par défaut':'date_pub','Télétravail':'teletravail','Management':'management','Employeur':'employeur','Catégorie':'categorie','Compétences attendues':'competences','Nature de contrat':'nature_contrat','Durée du contrat':'duree_contrat','Spécialisation':'specialisation'}
frames=[]
for f in sorted(glob.glob(os.path.join(src,'*.csv'))):
    df=pd.read_csv(f,sep=';',dtype=str,encoding='utf-8',on_bad_lines='skip',engine='python')
    keep=[c for c in cols if c in df.columns]; df=df[keep].rename(columns=cols); df['file']=os.path.basename(f)
    print(os.path.basename(f),len(df)); frames.append(df)
df=pd.concat(frames,ignore_index=True)
for c in ['date_first_pub','date_pub']:
    df[c]=pd.to_datetime(df[c],format='%d/%m/%Y',errors='coerce')
df['date_posted']=df['date_first_pub'].fillna(df['date_pub'])
before=len(df); df=df.drop_duplicates(subset=['ref']) ; print('dedup on ref',before,'->',len(df))
df['dept']=df['localisation'].str.extract(r'\((\d[0-9AB])\)')[0]
df['month']=df['date_posted'].dt.to_period('M').astype(str)
print(df.month.value_counts().sort_index().to_string()[:1500])
df.to_parquet(dst,index=False); print('written',dst,len(df))
