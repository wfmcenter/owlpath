import copy,json,tempfile,unittest,shutil
from pathlib import Path
from engine import Catalog,assess,make_plan,prereq_ready,completed_credits,DataError,PlanBlocked,verify_plan
from demo import build_student,advisor_markdown,load_example
from ai import evidence

CAT=Catalog()

def sample(name):return load_example(name)
def selected(p,g):return [c for b in p['group_choices'][g] for c in b]

class GenericEngineTests(unittest.TestCase):
 def test_catalog_and_sources(self):
  self.assertEqual(len(CAT.programs),3)
  self.assertGreaterEqual(len(CAT.courses),140)
  self.assertTrue(CAT.validate())
  self.assertEqual(CAT.programs['PSY_BA_2026']['total_degree_credits'],123)

 def test_cs_ba_bs_from_legacy_data(self):
  for pid in ['CS_BA_2026','CS_BS_2026']:
   student=sample('cs_ai');student['program_id']=pid
   for strategy in ['fastest','balanced','interest']:
    with self.subTest(pid=pid,strategy=strategy):
     p=make_plan(CAT,student,strategy)
     self.assertTrue(p['verification']['modeled_pass'],p['verification']['errors'])
     self.assertGreaterEqual(p['projected_total_credits'],123)
     self.assertTrue(p['verification']['manual_review'])

 def test_psychology_foundations_advanced_distinct(self):
  p=make_plan(CAT,sample('psy_neuro'),'interest')
  self.assertTrue(p['verification']['modeled_pass'])
  self.assertEqual(len(p['group_choices']['DCS']),2)
  self.assertEqual(len(p['group_choices']['BCS']),2)
  self.assertEqual(len(p['group_choices']['ADVANCED']),3)
  self.assertEqual(len(p['group_choices']['PSY_ELECTIVE']),1)
  self.assertEqual(len(set(selected(p,'ADVANCED')+selected(p,'PSY_ELECTIVE'))),4)
  self.assertIn('PSY4696',selected(p,'CAPSTONE'))

 def test_psychology_capstone_after_90_and_methods(self):
  s=sample('psy_neuro')
  for strategy in ['fastest','balanced','interest']:
   p=make_plan(CAT,s,strategy)
   credits=completed_credits(s); prior=set(x['course_id'] for x in s['completed_courses'])
   found=False
   for term in p['terms']:
    ids={i['id'] for i in term['items'] if i['kind']=='course'}
    if 'PSY4696' in ids:
     found=True
     self.assertGreaterEqual(credits,90)
     self.assertIn('PSY3096',prior)
    prior|=ids;credits+=term['credits']
   self.assertTrue(found)

 def test_psychology_interests_change_course_selection(self):
  a=sample('psy_neuro');b=sample('psy_clinical')
  self.assertEqual(a['completed_courses'],b['completed_courses'])
  p=make_plan(CAT,a,'interest');q=make_plan(CAT,b,'interest')
  self.assertNotEqual(selected(p,'ADVANCED'),selected(q,'ADVANCED'))
  self.assertTrue(p['verification']['prerequisites_valid'])
  self.assertTrue(q['verification']['prerequisites_valid'])

 def test_cs_interests_change_course_selection(self):
  a=sample('cs_ai');b=sample('cs_cyber')
  self.assertEqual(a['completed_courses'],b['completed_courses'])
  p=make_plan(CAT,a,'interest');q=make_plan(CAT,b,'interest')
  self.assertNotEqual(selected(p,'CS_ELECTIVES'),selected(q,'CS_ELECTIVES'))
  self.assertTrue(p['verification']['modeled_pass'])
  self.assertTrue(q['verification']['modeled_pass'])

 def test_unknown_math_blocks(self):
  r=assess(CAT,sample('psy_math_blocked'))
  self.assertTrue(all(not x['ok'] for x in r['plans'].values()))
  self.assertTrue(any('Statistics' in str(x['error']) or 'math' in str(x['error']).lower() for x in r['plans'].values()))

 def test_no_duplicate_semester_course_ids(self):
  for name in ['cs_ai','cs_cyber','psy_neuro','psy_clinical']:
   p=make_plan(CAT,sample(name),'interest')
   ids=[i['id'] for term in p['terms'] for i in term['items'] if i['kind']=='course']
   self.assertEqual(len(ids),len(set(ids)))

 def test_cannot_claim_verified_tuj_offerings(self):
  for name in ['cs_ai','psy_neuro']:
   p=make_plan(CAT,sample(name),'balanced')
   self.assertFalse(p['verification']['campus_offerings_verified'])
   self.assertIn('ADVISOR REVIEW',p['verification']['status'])
   self.assertGreater(p['verification']['provisional_slots'],0)

 def test_student_input_and_report_export(self):
  student=build_student(CAT,program_id='PSY_BA_2026',course_ids=['PSY1001'],
      grades={'PSY1001':'A'},gened_ids=['GW'],interests={'clinical':5},
      flags={'math_ready':True},other_credits=0)
  r=assess(CAT,student)
  self.assertTrue(r['plans']['interest']['ok'])
  md=advisor_markdown(CAT,r,'interest',{'status':'Revision requested','comment':'Check TUJ class rotation'})
  self.assertIn('Revision requested',md)
  self.assertIn('Check TUJ class rotation',md)
  self.assertIn('PROVISIONAL',md.upper())
  self.assertEqual(evidence(r,'interest')['program_id'],'PSY_BA_2026')
  self.assertNotIn('student_id',evidence(r,'interest'))

 def test_cannot_double_count_in_psy_groups(self):
  p=make_plan(CAT,sample('psy_neuro'),'interest')
  used=set()
  for g in CAT.programs['PSY_BA_2026']['groups']:
   for b in p['group_choices'][g['id']]:
    self.assertTrue(set(b).isdisjoint(used))
    used.update(b)

 def test_future_program_auto_discovery(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'catalog';shutil.copytree(CAT.path,dest)
   p=copy.deepcopy(CAT.programs['PSY_BA_2026']);p['program_id']='TEST_NEW_MAJOR_2026';p['major']='New major'
   (dest/'programs'/'TEST_NEW_MAJOR_2026.json').write_text(json.dumps(p))
   cat=Catalog(dest)
   self.assertIn('TEST_NEW_MAJOR_2026',cat.programs)
   s=sample('psy_neuro');s['program_id']='TEST_NEW_MAJOR_2026'
   self.assertTrue(make_plan(cat,s,'interest')['verification']['modeled_pass'])

 def test_early_capstone_detected_by_final_validator(self):
  s=sample('psy_neuro');p=make_plan(CAT,s,'interest');bad=copy.deepcopy(p)
  cap=None
  for sem in bad['terms']:
   for item in list(sem['items']):
    if item['id']=='PSY4696':sem['items'].remove(item);cap=item;break
  self.assertIsNotNone(cap)
  bad['terms'][0]['items'].append(cap)
  result=verify_plan(CAT,s,bad)
  self.assertFalse(result['modeled_pass'])
  self.assertTrue(any('PSY4696' in x for x in result['errors']))

 def test_cs_elective_limits_respected(self):
  p=make_plan(CAT,sample('cs_ai'),'interest')
  ids=selected(p,'CS_ELECTIVES')
  self.assertLessEqual(len(set(ids)&{'MATH2101','MATH2103','MATH2043'}),1)
  self.assertNotIn('CIS4398',ids)

 def test_unverified_advanced_psychology_not_selected(self):
  p=make_plan(CAT,sample('psy_neuro'),'interest')
  self.assertNotIn('PSY3413',selected(p,'ADVANCED'))
  self.assertNotIn('PSY3418',selected(p,'ADVANCED'))

 def test_invalid_program_fails_early(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'catalog';shutil.copytree(CAT.path,dest)
   p=copy.deepcopy(CAT.programs['PSY_BA_2026']);p['program_id']='BAD';p['groups'][0]['choices']=[['FAKE9999']]
   (dest/'programs'/'BAD.json').write_text(json.dumps(p))
   with self.assertRaises(DataError):Catalog(dest)

 def test_external_transcript_grade_not_silently_counted(self):
  s=sample('psy_neuro');s['completed_courses'][0]['grade']='F'
  # Course is no longer considered completed; planner must schedule a retake.
  p=make_plan(CAT,s,'interest')
  self.assertIn('PSY1001',[i['id'] for t in p['terms'] for i in t['items']])

if __name__=='__main__':unittest.main()
