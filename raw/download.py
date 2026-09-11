import json,time,urllib.request,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
rows=json.load(open(ROOT/'cdx_rows_raw.json'))[1:]
rows=[r for r in rows if not r[1].endswith('/embed/')]
out=ROOT/'all_html.json'
data=json.load(open(out)) if out.exists() else {}
for ts,url,*_ in rows:
    if url in data and len(data[url])>5000: continue
    u=f"https://web.archive.org/web/{ts}id_/{url}"
    for i in range(6):
        try:
            data[url]=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=90).read().decode('utf-8','replace')
            print(len(data[url]),url,flush=True); break
        except Exception as e:
            print('retry',i,url,e,flush=True); time.sleep(10*(i+1))
    json.dump(data,open(out,'w'),ensure_ascii=False)
    time.sleep(1.5)
json.dump(rows,open(ROOT/'cdx_rows.json','w'),ensure_ascii=False,indent=0)
print('done',len(data),'/',len(rows))
