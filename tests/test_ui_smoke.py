"""Headless execution of Streamlit script using a minimal fake UI.
Not a substitute for a real Streamlit browser test.
"""
import runpy,sys,types,unittest
from pathlib import Path

APP=Path(__file__).resolve().parents[1]/'app.py'
class FakeStreamlit(types.ModuleType):
 def __init__(self,fixture):
  super().__init__('streamlit');self.fixture=fixture;self.session_state={};self.sidebar=self;self.calls=[]
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def cache_resource(self,**kwargs):return lambda f:f
 def set_page_config(self,**kwargs):pass
 def columns(self,layout):return [self for _ in range(layout if isinstance(layout,int) else len(layout))]
 def expander(self,*args,**kwargs):return self
 def form(self,*args,**kwargs):return self
 def spinner(self,*args,**kwargs):return self
 def tabs(self,labels):return [self]*len(labels)
 def selectbox(self,label,options,index=0,**kwargs):
  if label=='Synthetic example':return self.fixture
  return options[index]
 def multiselect(self,label,options,default=None,**kwargs):return default or []
 def number_input(self,label,*args,**kwargs):return kwargs.get('value',args[-1] if args else 0)
 def slider(self,label,*args,**kwargs):return kwargs.get('value',args[-1] if args else 0)
 def checkbox(self,label,value=False,**kwargs):return value
 def radio(self,label,options,index=0,**kwargs):return options[index]
 def form_submit_button(self,*args,**kwargs):return True
 def button(self,*args,**kwargs):return False
 def text_input(self,label,value='',**kwargs):return value
 def text_area(self,label,value='',**kwargs):return value
 def download_button(self,*args,**kwargs):return False
 def link_button(self,*args,**kwargs):return False
 def stop(self):raise RuntimeError('Unexpected st.stop()')
 def __getattr__(self,name):
  if name.startswith('__'):raise AttributeError(name)
  def ignored(*args,**kwargs):
   self.calls.append(name)
   return None
  return ignored

class StreamlitControlFlowTests(unittest.TestCase):
 def test_ui_runs_with_cs_profile(self):self._run('cs_ai','CS_BS_2026')
 def test_ui_runs_with_psychology_profile(self):self._run('psy_neuro','PSY_BA_2026')
 def test_ui_blocks_unverified_placement(self):
  fake=self._run('psy_math_blocked','PSY_BA_2026')
  self.assertTrue(all(not v['ok'] for v in fake.session_state['owlpath_report']['plans'].values()))
 def _run(self,fixture,expected):
  fake=FakeStreamlit(fixture);before=sys.modules.get('streamlit');sys.modules['streamlit']=fake
  try:runpy.run_path(str(APP),run_name='__main__')
  finally:
   if before is None:sys.modules.pop('streamlit',None)
   else:sys.modules['streamlit']=before
  self.assertEqual(fake.session_state['owlpath_report']['program_id'],expected)
  return fake

if __name__=='__main__':unittest.main()
