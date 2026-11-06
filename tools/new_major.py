"""Scaffold a *draft* data file. Move it under catalog/programs only after populating and validating.
Usage: python tools/new_major.py --id SOC_BA_2026 --major Sociology --degree BA --template CLA_2026
"""
import argparse,json,pathlib,re
p=argparse.ArgumentParser()
p.add_argument('--id',required=True);p.add_argument('--major',required=True)
p.add_argument('--degree',required=True);p.add_argument('--template',required=True)
p.add_argument('--source-url',default='SOURCE_URL_REQUIRED')
a=p.parse_args()
if not re.fullmatch('[A-Z0-9_]+',a.id):p.error('Use uppercase letters/numbers/underscores in ID')
root=pathlib.Path(__file__).resolve().parent.parent
if not (root/'catalog'/'templates'/(a.template+'.json')).exists():p.error('Unknown template')
out=root/'drafts';out.mkdir(exist_ok=True)
target=out/(a.id+'.json')
if target.exists():p.error('Draft already exists')
obj={'program_id':a.id,'major':a.major,'degree':a.degree,'catalog_year':'2026-27',
 'total_degree_credits':123,'gened_template':a.template,'source_url':a.source_url,
 'min_grade':'C-','groups':[{'id':'REPLACE_ME','label':'One required course — replace',
                              'type':'choose','count':1,'choices':[['REPLACE_COURSE_ID']],'section':'major'}],
 'other_slots':[],'checks':[{'id':'academic_advisor_review','kind':'manual','reason':'Verify all program-specific rules and course offerings'}],
 'notes':['Data-inventory draft, not ready for planning']}
target.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
print('Created',target,'\nFill course metadata/prerequisites, replace sample group, then move to catalog/programs and run tests.')
