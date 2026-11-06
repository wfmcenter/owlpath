"""Presentation/reporting utilities independent of Streamlit and OpenAI."""
import json,hashlib,copy
from pathlib import Path
from engine import Catalog,assess,course_credits
ROOT=Path(__file__).resolve().parent

def load_example(name:str):
    file=ROOT/'samples'/f'{name}.json'
    return json.loads(file.read_text(encoding='utf-8'))

def profile_names():
    return sorted(p.stem for p in (ROOT/'samples').glob('*.json'))

def build_student(cat:Catalog,*,program_id,course_ids,grades=None,gened_ids=None,other_slots=None,
                  interests=None,careers=None,flags=None,target=15,campus='Tokyo',other_credits=0,temple_ids=None):
    if program_id not in cat.programs:raise ValueError('Invalid program')
    if len(course_ids)!=len(set(course_ids)):raise ValueError('Duplicate courses')
    if not 9<=int(target)<=21:raise ValueError('Target term credits must be 9–21')
    temple_ids=set(temple_ids if temple_ids is not None else course_ids)
    courses=[]
    for cid in course_ids:
        if cid not in cat.courses or course_credits(cat.courses[cid]) is None:raise ValueError('Unknown course/credits: '+cid)
        grade=(grades or {}).get(cid,'B')
        if grade not in ('A+','A','A-','B+','B','B-','C+','C','C-','D','F'):raise ValueError('Invalid grade: '+grade)
        courses.append({'course_id':cid,'grade':grade,'credits':course_credits(cat.courses[cid]),'at_temple':cid in temple_ids})
    prog=cat.programs[program_id];allowed={s['id'] for s in cat.templates[prog['gened_template']]['slots']}
    allowed|={s['id'] for s in prog.get('other_slots',[])}
    slots=set(gened_ids or [])|set(other_slots or [])
    if not slots.issubset(allowed):raise ValueError('Invalid completed slot: '+str(slots-allowed))
    # Category credits are provisional and counted once; retain sources in student input.
    slot_lookup={s['id']:s for s in cat.templates[prog['gened_template']]['slots']+prog.get('other_slots',[])}
    for sid in sorted(slots):
        courses.append({'course_id':sid+'_SLOT','grade':'B','credits':slot_lookup[sid]['credits'],'at_temple':True})
    weights={k:int(v) for k,v in (interests or {}).items() if k in cat.interest_labels}
    if any(not 0<=v<=5 for v in weights.values()):raise ValueError('Interest ratings must be 0..5')
    if not 0<=other_credits<=120:raise ValueError('Other credits out of range')
    return {'student_id':'SYNTHETIC_CUSTOM','program_id':program_id,'catalog_year':prog['catalog_year'],
            'campus_preference':campus,'completed_courses':courses,'other_completed_credits':int(other_credits),
            'preferences':{'target_credits_per_term':int(target),'interest_weights':weights,
                           'career_tags':[t for t in (careers or []) if t in cat.interest_labels]},
            'prototype_flags':dict(flags or {})}

def explain_locally(report,strategy,cat:Catalog):
    info=report['plans'][strategy]
    if not info['ok']:return 'No provisional plan could be generated: '+str(info['error'])
    p=info['plan'];s=report['student'];g=p['group_choices'];prog=cat.programs[p['program_id']]
    order=['fastest','balanced','interest'];label=['Prerequisite-first','Balanced workload','Interest-aligned'][order.index(strategy)]
    relevant=[]
    for group in prog['groups']:
        opts=g.get(group['id'],[])
        if (group['type']=='credits' or (group['type']=='choose' and int(group['count'])>1)) and opts:
            relevant.append(f"{group['label']}: " + ', '.join(' + '.join(b) for b in opts[:5]))
    text=f'**{label}.** The engine applies the academic rules in `{p["program_id"]}` and sequences eligible courses after their prerequisites. '
    if strategy=='interest':text+='Elective and choice-group ranking uses 70% declared interest levels and 30% selected career tags. '
    elif strategy=='balanced':text+='Scheduling limits the number of modeled academic courses per term and fills remaining credits with provisional slots. '
    else:text+='Scheduling prioritizes courses that unlock downstream prerequisites. '
    text+='**Selected group examples:** '+('; '.join(relevant[:3]) if relevant else 'No optional groups')+'. '
    text+='The resulting terms are relative, not verified TUJ offerings; advisor review remains necessary.'
    return text

def advisor_markdown(cat,report,strategy,review=None):
    info=report['plans'][strategy];p=cat.programs[report['program_id']]
    lines=[f'# OwlPath — Provisional Advising Brief',f'',f'Program: {p["major"]} {p["degree"]} ({p["catalog_year"]})',
     f'Pathway: {strategy}',f'Student record: **SYNTHETIC** (no university system connection)', '',
     f'**Not a degree audit or verified TUJ course schedule.**','']
    if not info['ok']:
        lines+=['## Blocked',str(info['error']),'']
    else:
        pl=info['plan'];v=pl['verification']
        lines +=[f'## Modeled result: {v["status"]}',
           f'Projected credits: {pl["projected_total_credits"]}; relative terms: {len(pl["terms"])}',
           f'Placeholder slots: {v["provisional_slots"]}; manual checks: {len(v["manual_review"])}','',
           '## Semester sequence']
        for sem in pl['terms']:
            lines.append(f'### Relative term {sem["term"]} ({sem["credits"]:g} credits)')
            for item in sem['items']:
                lines.append(f'- {item["id"]}: {item["title"]} — {item["credits"]:g} credits'+(' [PLACEHOLDER]' if item['kind']!='course' else ''))
        lines+=['','## Academic validation','']
        for g in v['group_results']:
            lines.append(f'- {g["label"]}: {"model-pass" if g["passed"] else "failed"} ({g["course_count"]} choices)')
        lines+=['','## Manual review','']
        for x in v['manual_review']:lines.append('- '+x)
        lines+=['','## Source / availability warnings',
                '- Actual semester offerings by TUJ campus are NOT validated.',
                '- Some general education, foreign-language and free-elective credits are placeholders, not registered courses.',
                '- College-wide and residency rules require confirmation from official student records.',
                '- The University Bulletin is subject to amendment and individual exceptions.']
    review=review or {}
    lines+=['','## Advisor notes (demonstration only)',
            'Status: '+str(review.get('status','Not reviewed')),
            'Comments: '+str(review.get('comment','None'))]
    return '\n'.join(lines)+'\n'

def fingerprint(report,strategy):
    blob=json.dumps({'program_id':report['program_id'],'student':report['student'],'strategy':strategy},sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
