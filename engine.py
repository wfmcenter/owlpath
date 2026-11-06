"""OwlPath data-driven academic pathway engine.
No major, department, course code, prerequisite, or GenEd rule is embedded in the runtime.
All academic facts are loaded from catalog JSON files.

This engine generates *provisional* plans, not certified degree audits.
"""
from __future__ import annotations
import copy, json, math
from dataclasses import dataclass
from pathlib import Path
from itertools import combinations
from typing import Any

BASE = Path(__file__).resolve().parent
GRADE_INDEX = {g:i for i,g in enumerate(['F','D-','D','D+','C-','C','C+','B-','B','B+','A-','A','A+'])}

class DataError(ValueError):pass
class PlanBlocked(ValueError):pass

def course_credits(course):
    x = course.get('credits')
    return float(x) if x is not None else None

def passed(row,minimum='C-'):
    return GRADE_INDEX.get(str(row.get('grade','')).upper(),-1)>=GRADE_INDEX[minimum]

class Catalog:
    def __init__(self, path:Path|str=BASE/'catalog'):
        self.path=Path(path)
        self.courses=json.loads((self.path/'courses.json').read_text(encoding='utf-8'))
        self.prereqs=json.loads((self.path/'prerequisites.json').read_text(encoding='utf-8'))
        self.templates={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (self.path/'templates').glob('*.json')}
        self.programs={}
        for p in sorted((self.path/'programs').glob('*.json')):
            obj=json.loads(p.read_text(encoding='utf-8'))
            if obj['program_id'] in self.programs: raise DataError('Duplicate program ID: '+obj['program_id'])
            self.programs[obj['program_id']]=obj
        self.interest_labels=json.loads((self.path/'interest_labels.json').read_text(encoding='utf-8'))
        self.validate()

    def validate(self):
        if not self.programs:raise DataError('No program files found')
        for pid,p in self.programs.items():
            if p['gened_template'] not in self.templates:raise DataError(f'{pid}: unknown GenEd template')
            ids=set()
            for group in p['groups']:
                gid=group['id']
                if gid in ids:raise DataError(f'{pid}: duplicate group {gid}')
                ids.add(gid)
                if group['type'] not in ('choose','credits'):raise DataError(f'{pid}.{gid}: unsupported type')
                if not group.get('choices'):raise DataError(f'{pid}.{gid}: no choices')
                if group['type']=='choose' and (int(group['count'])<1 or int(group['count'])>len(group['choices'])):raise DataError(f'{pid}.{gid}: invalid count')
                for bundle in group['choices']:
                    if not isinstance(bundle,list) or not bundle:raise DataError(f'{pid}.{gid}: bad bundle')
                    for cid in bundle:
                        if cid not in self.courses:raise DataError(f'{pid}.{gid}: missing course {cid}')
        for cid,record in self.courses.items():
            if record['id']!=cid:raise DataError('Course key mismatch '+cid)
            cr=course_credits(record)
            if cr is not None and cr<=0:raise DataError('Invalid course credits '+cid)
        for pid,program in self.programs.items():
            for group in program['groups']:
                if group['type']=='credits' and float(group['min_credits'])>float(group['max_credits']):
                    raise DataError(f'{pid}/{group["id"]}: impossible credit bounds')
                for limit in group.get('limits',[]):
                    if any(cid not in self.courses for cid in limit['choices']):
                        raise DataError(f'{pid}/{group["id"]}: unknown limit-course ID')
        for name,template in self.templates.items():
            slots=[x['id'] for x in template['slots']]
            if len(slots)!=len(set(slots)):raise DataError('Duplicate slot in '+name)
            if any(float(s['credits'])<=0 for s in template['slots']):raise DataError('Invalid GenEd credit in '+name)
        def check_expr(expr):
            keys=set(expr)
            allowed={'any','all','course','flag','subject_level','min_prior_credits'}
            if len(keys)!=1 or not keys.issubset(allowed):raise DataError('Unsupported prerequisite expression: '+str(expr))
            if 'any' in expr or 'all' in expr:
                subs=expr.get('any',expr.get('all',[]))
                if not subs:raise DataError('Empty prerequisite expression')
                for child in subs:check_expr(child)
            if 'min_prior_credits' in expr and float(expr['min_prior_credits'])<0:
                raise DataError('Negative prior credit requirement')
        for target,expr in self.prereqs.items():
            if target not in self.courses:raise DataError('Prerequisite target not in course table: '+target)
            check_expr({'all':expr['all']}) if expr.get('all') else None
        return True

def student_courses(student,minimum='C-'):
    return {r['course_id']:r for r in student.get('completed_courses',[]) if passed(r,minimum)}

def completed_credits(student):
    return sum(float(r.get('credits',0)) for r in student.get('completed_courses',[]) if passed(r)) + float(student.get('other_completed_credits',0))

def interest_points(cat,student,course_id):
    c=cat.courses[course_id]
    weights=student.get('preferences',{}).get('interest_weights',{})
    career=set(student.get('preferences',{}).get('career_tags',[]))
    return round(sum(float(v) * (.7*float(weights.get(k,0))/5 + .3*(k in career)) for k,v in c.get('tags',{}).items()),3)

def _ready_cond(cond,completed,credits_before,student,cat):
    if 'course' in cond:return cond['course'] in completed
    if 'flag' in cond:return bool(student.get('prototype_flags',{}).get(cond['flag'],False))
    if 'min_prior_credits' in cond:return credits_before >= float(cond['min_prior_credits'])
    if 'subject_level' in cond:
        info=cond['subject_level']; low=int(info.get('min_level',0)); high=int(info.get('max_level',9999));subj=info['subject']
        return any(cat.courses.get(c,{}).get('subject')==subj and low<=int(cat.courses[c]['level'])<=high for c in completed)
    if 'any' in cond:return any(_ready_cond(c,completed,credits_before,student,cat) for c in cond['any'])
    if 'all' in cond:return all(_ready_cond(c,completed,credits_before,student,cat) for c in cond['all'])
    raise DataError('Unsupported prerequisite expression: '+str(cond))

def prereq_ready(cat, student, cid, completed, credits_before):
    rule=cat.prereqs.get(cid)
    return not rule or _ready_cond(rule,completed,credits_before,student,cat)

def _deps_for(cond,known,student,cat,stack=None):
    """Find missing course IDs needed for a condition; raises for unconfirmed flags.
    Conservative dependency-closure choice: min added course count, no fabricated course IDs.
    """
    stack=stack or set()
    if _ready_cond(cond,known,0,student,cat):return set()
    if 'min_prior_credits' in cond:return set() # term-level credit gate is scheduled, not waived
    if 'flag' in cond:raise PlanBlocked('Unconfirmed eligibility flag: '+cond['flag'])
    if 'course' in cond:
        cid=cond['course']
        if cid in known:return set()
        if cid not in cat.courses or course_credits(cat.courses[cid]) is None:
            raise PlanBlocked('Prerequisite has no verified course record: '+cid)
        if cid in stack:raise PlanBlocked('Prerequisite cycle at '+cid)
        closure={cid}
        for sub in cat.prereqs.get(cid,{}).get('all',[]):
            closure|=_deps_for(sub,known|closure,student,cat,stack|{cid})
        return closure
    if 'subject_level' in cond:
        info=cond['subject_level']
        candidates=[c for c,v in cat.courses.items() if v.get('subject')==info['subject'] and
         int(info.get('min_level',0))<=v['level']<=int(info.get('max_level',9999)) and
         course_credits(v) is not None and not v.get('honors_only',False)]
        if not candidates:raise PlanBlocked('No verified course available for subject-level prerequisite')
        # Match current student interests, preferring previously chosen eligible foundation courses.
        candidates.sort(key=lambda c:(-interest_points(cat,student,c),c))
        opts=[]
        for c in candidates[:12]:
            try:opts.append((_deps_for({'course':c},known,student,cat,stack),c))
            except PlanBlocked:continue
        if not opts:raise PlanBlocked('No eligible subject-level prerequisite')
        opts.sort(key=lambda x:(len(x[0]),-interest_points(cat,student,x[1]),x[1]))
        return opts[0][0]
    if 'all' in cond:
        result=set()
        for x in cond['all']:result|=_deps_for(x,known|result,student,cat,stack)
        return result
    if 'any' in cond:
        options=[]
        for x in cond['any']:
            try:
                new=_deps_for(x,known,student,cat,stack)
                if any(cat.courses[c].get('honors_only',False) and not student.get('prototype_flags',{}).get('honors_approved',False) for c in new):continue
                options.append(new)
            except PlanBlocked:continue
        if not options:raise PlanBlocked('No feasible alternative prerequisite for '+str(cond))
        options.sort(key=lambda x:(len(x),sum(course_credits(cat.courses[c]) or 0 for c in x), sorted(x)))
        return options[0]
    raise DataError('Unsupported dependency '+str(cond))

def _choice_is_usable(cat,student,bundle):
    for cid in bundle:
        if cid not in cat.courses:return False
        c=cat.courses[cid]
        if course_credits(c) is None or not c.get('metadata_verified',True):return False
        if c.get('honors_only',False) and not student.get('prototype_flags',{}).get('honors_approved',False):return False
        rule=cat.prereqs.get(cid,{})
        for expr in rule.get('all',[]):
            if 'flag' in expr and not student.get('prototype_flags',{}).get(expr['flag'],False):return False
    return True

def _rank_bundle(cat,student,bundle,strategy,known):
    fresh=[c for c in bundle if c not in known]
    pref=sum(interest_points(cat,student,c) for c in fresh)
    dep=0
    for cid in fresh:
        for expr in cat.prereqs.get(cid,{}).get('all',[]):
            try:dep+=len(_deps_for(expr,known|set(bundle),student,cat))
            except PlanBlocked:dep+=30
    if strategy=='interest':return 14*pref-3*dep-len(fresh)
    if strategy=='balanced':return -4*dep - sum(course_credits(cat.courses[c]) or 0 for c in fresh)*.2 + pref*.1
    return -6*dep + pref*.05

def _choose_bundle_group(cat,student,group,known,used,strategy):
    needed=int(group['count']);selected=[]
    # Completed course may satisfy this particular group, but cannot count twice in separate groups.
    for bundle in group['choices']:
        if len(selected)>=needed:break
        if all(c in known and c not in used for c in bundle):
            selected.append(bundle);used.update(bundle)
    opts=[]
    for b in group['choices']:
        if any(c in used for c in b):continue
        if not _choice_is_usable(cat,student,b):continue
        try:
            deps=set()
            for cid in b:
                for expr in cat.prereqs.get(cid,{}).get('all',[]):deps|=_deps_for(expr,known|set(b),student,cat)
        except PlanBlocked:continue
        opts.append((_rank_bundle(cat,student,b,strategy,known)-.1*len(deps),b))
    opts.sort(key=lambda x:(-x[0],x[1]))
    for _,bundle in opts:
        if len(selected)>=needed:break
        if any(c in used for c in bundle):continue
        selected.append(bundle);used.update(bundle)
    if len(selected)<needed:
        raise PlanBlocked(f'{group["label"]}: only {len(selected)}/{needed} verified distinct course options available')
    return selected

def _choose_credit_group(cat,student,group,known,used,strategy):
    low=float(group['min_credits']);hi=float(group.get('max_credits',low+2))
    completed=[];existing=0
    for b in group['choices']:
        if all(c in known and c not in used for c in b):
            completed.append(b);used.update(b);existing+=sum(course_credits(cat.courses[c]) for c in b)
    if existing>=low:return completed
    candidates=[]
    for bundle in group['choices']:
        if any(c in used for c in bundle) or not _choice_is_usable(cat,student,bundle):continue
        credits=sum(course_credits(cat.courses[c]) for c in bundle)
        if not credits:continue
        try:
            extra=set()
            for cid in bundle:
                for expr in cat.prereqs.get(cid,{}).get('all',[]):extra|=_deps_for(expr,known|set(bundle),student,cat)
        except PlanBlocked:continue
        score=_rank_bundle(cat,student,bundle,strategy,known)-.5*len(extra)
        candidates.append((score,bundle,credits))
    candidates.sort(key=lambda x:-x[0]);candidates=candidates[:24]
    best=None
    # cap choose 6 for 15/16-credit electives; all generic, no course-specific exclusions.
    for size in range(1,min(7,len(candidates)+1)):
        for combo in combinations(candidates,size):
            total=existing+sum(x[2] for x in combo)
            if not low<=total<=hi:continue
            ids=[cid for x in combo for cid in x[1]]
            if len(ids)!=len(set(ids)):continue
            if any(sum(1 for c in ids if c in set(lim['choices']))>int(lim.get('max_courses',999)) for lim in group.get('limits',[]) if 'max_courses' in lim):continue
            if any(sum((course_credits(cat.courses[c]) or 0) for c in ids if c in set(lim['choices']))>float(lim['max_credits']) for lim in group.get('limits',[]) if 'max_credits' in lim):continue
            score=sum(x[0] for x in combo)
            candidate=(score,-len(ids),[x[1] for x in combo])
            if best is None or candidate[:2]>best[:2]:best=candidate
    if best is None:raise PlanBlocked(group['label']+': no combination meets the credit range')
    for b in best[2]:used.update(b)
    return completed+best[2]

def select_curriculum(cat,student,strategy):
    prog=cat.programs[student['program_id']]
    done=student_courses(student,prog.get('min_grade','C-'))
    selected=set(done);used=set();bundles=[]; selected_groups={}
    # Academic groups are ordered in the program data, but no major-specific logic.
    for g in prog['groups']:
        if g['type']=='choose':chosen=_choose_bundle_group(cat,student,g,selected,used,strategy)
        else:chosen=_choose_credit_group(cat,student,g,selected,used,strategy)
        selected_groups[g['id']]=chosen
        for b in chosen: selected.update(b); bundles.append((g,b))
    # Complete all prerequisite closure for selected courses.
    max_iter=100
    for _ in range(max_iter):
        extra=set()
        for cid in sorted(selected-set(done)):
            for expr in cat.prereqs.get(cid,{}).get('all',[]):
                try:extra|=_deps_for(expr,selected|extra,student,cat)
                except PlanBlocked as ex:raise PlanBlocked(f'{cid}: {ex}')
        new=extra-selected
        if not new:break
        selected|=new
    else:raise PlanBlocked('Exceeded prerequisite closure iterations')
    # Determine provisional GenEd + university slots.
    template=cat.templates[prog['gened_template']]
    completed_slots=set(student.get('completed_slots',[]))
    for row in student.get('completed_courses',[]):
        if row['course_id'].endswith('_SLOT'):completed_slots.add(row['course_id'][:-5])
    slots=[]
    for s in template['slots']:
        if s['id'] not in completed_slots:
            slots.append({'id':s['id']+'_SLOT','title':'GenEd: '+s['label']+' (provisional slot)',
             'credits':float(s['credits']),'kind':'gened_slot','reason':s['id']})
    for s in prog.get('other_slots',[]):
        if s['id'] in completed_slots or (s.get('waive_flag') and student.get('prototype_flags',{}).get(s['waive_flag'],False)):continue
        slots.append({'id':s['id']+'_SLOT','title':s['label'],'credits':float(s['credits']),'kind':'other_slot','reason':s['id']})
    real_needed=selected-set(done)
    known_credits=sum(float(done[c].get('credits',0)) for c in done)+float(student.get('other_completed_credits',0))
    real_credits=sum(course_credits(cat.courses[c]) or 0 for c in real_needed)
    remaining=math.ceil(float(prog['total_degree_credits'])-known_credits-real_credits-sum(s['credits'] for s in slots))
    # Free electives are labeled placeholders and not treated as real course credits for verification.
    k=1
    while remaining>0:
        cr=min(3,remaining)
        slots.append({'id':f'FREE_{k:03d}_SLOT','title':'Free elective credit placeholder (course TBD)',
                      'credits':cr,'kind':'free_slot','reason':'Credits only; not a course'})
        remaining-=cr;k+=1
    return prog,done,real_needed,slots,selected_groups

def _dependency_count(cat,course,real_needed):
    return sum(str(course) in json.dumps(cat.prereqs.get(other,{})) for other in real_needed if other!=course)

def make_plan(cat:Catalog,student:dict,strategy='balanced',max_terms=16):
    if strategy not in ('fastest','balanced','interest'):raise ValueError('Invalid strategy')
    if student['program_id'] not in cat.programs:raise ValueError('Unknown program: '+student['program_id'])
    target=int(student.get('preferences',{}).get('target_credits_per_term',15))
    if not 9<=target<=21:raise ValueError('Target credits must be between 9 and 21')
    prog,done,remaining,slots,selected_groups=select_curriculum(cat,student,strategy)
    prior=set(done); credits_before=completed_credits(student);terms=[]
    ordered={}
    for group in prog['groups']:
        if group.get('bundle_order')=='separate_terms':
            for bundle in selected_groups[group['id']]:
                # For a sequence of two 4-credit science courses, later item may not be in same term.
                for i in range(1,len(bundle)):ordered.setdefault(bundle[i],[]).append(bundle[i-1])
    remaining=set(remaining)
    slotq=list(slots)
    for term_no in range(1,max_terms+1):
        if not remaining and not slotq:break
        term=[];taken_this=set();budget=target
        def can_add(cid):
            if course_credits(cat.courses[cid]) is None:return False
            if not prereq_ready(cat,student,cid,prior,credits_before):return False
            return all(pre in prior for pre in ordered.get(cid,[]))
        ready=[c for c in remaining if can_add(c)]
        # Courses unlocking more classes are scheduled before soft interest preferences.
        ready.sort(key=lambda c:(-_dependency_count(cat,c,remaining),
         - (interest_points(cat,student,c) if strategy=='interest' else 0),
         int(cat.courses[c]['level']), c))
        if strategy=='balanced':major_limit=3
        elif strategy=='interest':major_limit=4
        else:major_limit=6
        for cid in ready:
            credit=course_credits(cat.courses[cid])
            if credit>budget or len(taken_this)>=major_limit:continue
            # Avoid overscheduling capstones with senior credit gates (condition is checked above).
            term.append({'id':cid,'title':cat.courses[cid]['title'],'credits':credit,
                         'kind':'course','reason':'Academic requirement / prerequisite / chosen elective',
                         'interest_points':interest_points(cat,student,cid)})
            taken_this.add(cid);budget-=credit
        # Keep free/GenEd slots staggered; no two courses that depend on one another in same term.
        while slotq:
            fit=next((i for i,s in enumerate(slotq) if s['credits']<=budget),None)
            if fit is None:break
            s=slotq.pop(fit);term.append(s);budget-=s['credits']
        if not term:
            # If courses are blocked solely by a 90-credit capstone gate, insufficient remaining
            # approved/placeholder credits must not create an infinite loop.
            if remaining:raise PlanBlocked('No eligible courses or slots in term '+str(term_no)+': '+', '.join(sorted(remaining)))
            break
        for cid in taken_this:remaining.remove(cid)
        terms.append({'term':term_no,'credits':round(sum(i['credits'] for i in term),2),'items':term})
        credits_before+=sum(i['credits'] for i in term)
        prior.update(taken_this)
    if remaining or slotq:raise PlanBlocked('Could not fit all modeled requirements within '+str(max_terms)+' terms: '+', '.join(sorted(remaining)))
    result={'strategy':strategy,'program_id':prog['program_id'],'terms':terms,
      'completed_credits':round(completed_credits(student),2),
      'projected_total_credits':round(credits_before,2),
      'group_choices':{k:[list(b) for b in bs] for k,bs in selected_groups.items()}}
    result['verification']=verify_plan(cat,student,result)
    return result

def verify_plan(cat,student,plan):
    prog=cat.programs[student['program_id']]
    prior=set(student_courses(student,prog.get('min_grade','C-')))
    earned=completed_credits(student)
    violations=[];slots=[];planned=[]
    for term in plan['terms']:
        for item in term['items']:
            if item['kind']=='course':
                cid=item['id'];planned.append(cid)
                if not prereq_ready(cat,student,cid,prior,earned):violations.append(f'{cid} in term {term["term"]} violates prerequisite / prior-credit rule')
            else:slots.append(item['id'])
        prior.update(i['id'] for i in term['items'] if i['kind']=='course')
        earned+=sum(i['credits'] for i in term['items'])
    # Ordered bundles are a conservative modeling choice stored in the degree data.
    placement={i['id']:t['term'] for t in plan['terms'] for i in t['items'] if i['kind']=='course'}
    for group in prog['groups']:
        if group.get('bundle_order')=='separate_terms':
            for bundle in plan['group_choices'].get(group['id'],[]):
                for i in range(1,len(bundle)):
                    before=placement.get(bundle[i-1],0)
                    after=placement.get(bundle[i],0)
                    if after and before>=after:
                        violations.append(f'{bundle[i]} must be placed after {bundle[i-1]} under {group["id"]} sequencing policy')
    groups=[];claimed=set();done=set(student_courses(student,prog.get('min_grade','C-')))
    for g in prog['groups']:
        selected=plan['group_choices'].get(g['id'],[])
        counted=[];count_credits=0
        for bundle in selected:
            if all(c in prior for c in bundle) and all(c not in claimed for c in bundle):
                claimed.update(bundle);counted.append(bundle)
                count_credits+=sum(course_credits(cat.courses[c]) or 0 for c in bundle)
        if g['type']=='choose':ok=len(counted)>=int(g['count'])
        else:ok=float(g['min_credits'])<=count_credits<=float(g.get('max_credits',1e9))
        counted_ids=[c for bundle in counted for c in bundle]
        for limit in g.get('limits',[]):
            ids=[c for c in counted_ids if c in set(limit['choices'])]
            if 'max_courses' in limit and len(ids)>int(limit['max_courses']):ok=False
            if 'max_credits' in limit and sum(course_credits(cat.courses[c]) or 0 for c in ids)>float(limit['max_credits']):ok=False
        groups.append({'id':g['id'],'label':g['label'],'passed':ok,'course_count':len(counted),'credits':count_credits})
    # Verify major credit minimum from courses explicitly assigned to major groups only.
    major_ids=set()
    for g in prog['groups']:
        if g.get('section')=='major':
            for b in plan['group_choices'].get(g['id'],[]):major_ids.update(b)
    major_credit=sum((course_credits(cat.courses[c]) or 0) for c in major_ids if c in prior)
    checks=[]
    for c in prog.get('checks',[]):
        kind=c['kind'];status='manual';value=None
        if kind=='major_credits':value=major_credit;status='passed' if value>=float(c['min_credits']) else 'failed'
        elif kind=='courses_complete':
            ok=all(x in prior for x in c['courses']) and (not c.get('and_one_of') or any(x in prior for x in c['and_one_of']))
            status='passed' if ok else 'failed';value=ok
        elif kind=='slot_or_flag':
            ok=bool(student.get('prototype_flags',{}).get(c['flag'],False)) or (c['slot_id']+'_SLOT' in slots) or c['slot_id'] in student.get('completed_slots',[])
            status='provisional' if ok else 'failed';value=ok
        elif kind=='credits_scope':
            # Without verified university metadata for all filler/transfer slots, never assert satisfied.
            value='Insufficient verified subject/school metadata for all academic credits.'
        elif kind=='residency':
            # Planned future Temple attendance cannot be verified at proposal stage.
            value='Requires eventual confirmation of course location and student record.'
        elif kind=='manual':value=c.get('reason','Advisor confirmation required')
        checks.append({'id':c['id'],'kind':kind,'status':status,'result':value})
    allgroups=all(g['passed'] for g in groups)
    cred_ok=earned>=float(prog['total_degree_credits'])
    manual=[x['id'] for x in checks if x['status'] in ('manual','provisional')]
    errors=(violations + [g['id']+' failed' for g in groups if not g['passed']]
       + ([] if cred_ok else ['Total credit minimum not met'])
       + [c['id']+' failed' for c in checks if c['status']=='failed'])
    return {'modeled_pass':not errors,'prerequisites_valid':not violations,'group_results':groups,
      'checks':checks,'manual_review':manual,'errors':errors,'projected_credits':round(earned,2),
      'provisional_slots':len(slots),'campus_offerings_verified':False,
      'status':'MODELED PASS — ADVISOR REVIEW REQUIRED' if not errors else 'BLOCKED — MODEL VALIDATION FAILED'}

def assess(cat,student):
    if student['program_id'] not in cat.programs:raise ValueError('Unknown program')
    res={'program':cat.programs[student['program_id']]['major']+' '+cat.programs[student['program_id']]['degree'],
      'program_id':student['program_id'],'student':student,'plans':{},
      'notice':'Synthetic/provisional decision-support only; not an official graduation audit.'}
    for s in ('fastest','balanced','interest'):
        try:
            p=make_plan(cat,student,s)
            res['plans'][s]={'ok':p['verification']['modeled_pass'],'plan':p,'error':None}
        except (PlanBlocked,DataError,ValueError) as exc:
            res['plans'][s]={'ok':False,'plan':None,'error':str(exc)}
    return res
