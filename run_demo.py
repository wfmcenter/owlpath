"""Offline demonstration and regression-output generator; Streamlit not required."""
import argparse,json
from pathlib import Path
from engine import Catalog,assess
from demo import load_example,advisor_markdown,profile_names

p=argparse.ArgumentParser(description='OwlPath data-driven academic pathway demo')
p.add_argument('--profile',choices=profile_names(),default='psy_neuro')
p.add_argument('--output-dir',default='outputs')
args=p.parse_args()
cat=Catalog();student=load_example(args.profile);result=assess(cat,student)
out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
(out/f'{args.profile}_report.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
for strategy,detail in result['plans'].items():
    (out/f'{args.profile}_{strategy}_advising_brief.md').write_text(advisor_markdown(cat,result,strategy),encoding='utf-8')
    if detail['ok']:
        plan=detail['plan']
        print(f'{args.profile:<22} {strategy:<10} MODELED PASS  {len(plan["terms"])} relative terms  '
              f'{plan["projected_total_credits"]} projected credits  {plan["verification"]["provisional_slots"]} placeholders')
    else:print(f'{args.profile:<22} {strategy:<10} BLOCKED: {detail["error"]}')
