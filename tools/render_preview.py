"""Creates an honest static visual preview from planner outputs (NOT native Streamlit)."""
import html,json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Catalog,make_plan
from demo import load_example
root=Path(__file__).resolve().parents[1]
cat=Catalog()
cases=[('Computer Science · AI-focused','cs_ai'),('Psychology · Neuroscience','psy_neuro'),('Psychology · Clinical','psy_clinical')]
cards=[]
for label,name in cases:
    s=load_example(name);p=make_plan(cat,s,'interest');v=p['verification']
    groups=[]
    for g in cat.programs[s['program_id']]['groups']:
        bs=p['group_choices'].get(g['id'],[])
        if len(g['choices'])>1 and (int(g.get('count',1))>1 or g['type']=='credits'):
            groups.append(f'<li><strong>{html.escape(g["label"])}</strong><span>{html.escape(", ".join(" + ".join(b) for b in bs))}</span></li>')
    terms=[]
    for t in p['terms'][:3]:
        lines=''.join(f'<li>{html.escape(i["id"])} <small>{html.escape(i["title"])}</small><b>{i["credits"]:g} cr</b></li>' for i in t['items'])
        terms.append(f'<div class="term"><h4>Relative term {t["term"]}<em>{t["credits"]:g} credits</em></h4><ul>{lines}</ul></div>')
    cards.append(f'''<section><div class="head"><h2>{html.escape(label)}</h2><span class="tag">{html.escape(s['program_id'])}</span></div>
      <div class="stats"><div><b>{len(p['terms'])}</b><small>relative terms</small></div><div><b>{p['projected_total_credits']:g}</b><small>projected credits</small></div>
        <div><b>{v['provisional_slots']}</b><small>unresolved course slots</small></div></div>
       <p class="notice">{html.escape(v['status'])} · TUJ availability unverified · advisor review required</p>
       <div class="columns"><div><h3>Selected requirement choices</h3><ul class="groups">{''.join(groups)}</ul></div>
        <div><h3>First three relative terms</h3>{''.join(terms)}</div></div></section>''')
page='''<!doctype html><html><head><meta charset="utf-8"><title>OwlPath · Model output preview</title>
<style>body{font:15px system-ui,Arial;color:#182844;margin:0;background:#f3f6fb}
main{max-width:1060px;margin:auto;padding:40px 22px}h1{font-size:31px;margin:0}h3{font-size:15px;margin:0 0 12px}
p.subtitle{color:#5f6d83;margin:9px 0 28px}section{background:white;border:1px solid #dde5f0;border-radius:14px;padding:24px;margin:0 0 28px;box-shadow:0 5px 20px #0b234006}.head{display:flex;align-items:center;justify-content:space-between}.head h2{font-size:20px;margin:0 0 12px}.tag{font-size:12px;background:#e9eef8;padding:6px 9px;border-radius:6px}
.stats{display:flex;gap:12px;margin:12px 0}.stats>div{padding:12px 22px;border-radius:9px;background:#f1f5fb;display:flex;flex-direction:column;min-width:100px}.stats b{font-size:24px}.stats small{font-size:12px;color:#526680}.notice{padding:11px 13px;color:#6e5106;background:#fff4d5;border-radius:7px;font-size:12px}.columns{display:grid;grid-template-columns:1fr 1.2fr;gap:28px;margin-top:20px}
.groups{padding:0;list-style:none}.groups li{border-bottom:1px solid #edf0f6;padding:9px 0;display:flex;flex-direction:column;gap:4px}.groups span{font-size:12px;color:#586a83;line-height:1.5}
.term{padding:10px 14px;border-radius:9px;border:1px solid #e1e8f0;margin-bottom:9px}.term h4{margin:0 0 9px;font-size:14px}.term em{float:right;font-style:normal;color:#586a83}.term ul{padding:0;margin:0;list-style:none}.term li{display:flex;gap:10px;border-top:1px solid #f0f2f7;padding:5px 0;font-size:12px}.term small{flex:1;color:#50617a}.term b{font-size:12px;white-space:nowrap}
footer{color:#65748c;font-size:12px} @media(max-width:700px){.columns{grid-template-columns:1fr}.stats{flex-wrap:wrap}}</style></head><body>
<main><h1>🦉 OwlPath / Output preview</h1><p class="subtitle">Generated from the actual generic Python engine. Static HTML preview, not a live Streamlit session.</p>'''+''.join(cards)+'''<footer>All profiles are synthetic; catalog-based relative term plans contain GenEd/free credit slots. Do not treat as official course availability or certified graduation.</footer></main></body></html>'''
out=root/'outputs'/'model_output_preview.html';out.write_text(page,encoding='utf-8');print(out)
