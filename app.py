"""Data-driven OwlPath Streamlit demonstration.
Adding another major requires catalog/programs/*.json and course metadata, not app edits.
"""
from __future__ import annotations
import json,os
from pathlib import Path
import streamlit as st
from engine import Catalog,assess,course_credits
from demo import build_student,profile_names,load_example,advisor_markdown,explain_locally,fingerprint
from ai import explain_with_openai

st.set_page_config(page_title='OwlPath | TUJ Academic Planning',page_icon='🦉',layout='wide')
st.markdown('''<style>
.block-container{padding-top:1.6rem;max-width:1300px}
[data-testid="stMetricValue"]{font-size:1.7rem}
.small-muted{color:#627189;font-size:0.91rem}
hr{margin:1rem 0}
</style>''',unsafe_allow_html=True)

@st.cache_resource(show_spinner=False)
def get_catalog():
    return Catalog()

try:cat=get_catalog()
except Exception as exc:
    st.error('Catalog data could not be validated: '+str(exc));st.stop()

st.title('🦉 OwlPath')
st.caption('Personalized academic pathways · Temple University Japan Campus · academic demonstration only')
st.warning('**Provisional decision-support, not official degree advising.** Future TUJ offerings, transfer equivalencies, university exceptions and advisor approval are not verified. Use only synthetic student records in this demo.')

# All academic programs, templates, fields, interests and choices come from files.
programs=sorted(cat.programs)
labels={pid:f"{cat.programs[pid]['major']} · {cat.programs[pid]['degree']} · {cat.programs[pid]['catalog_year']}" for pid in programs}
with st.sidebar:
    st.header('Dataset & student')
    st.caption(f'{len(programs)} programs · {len(cat.courses)} unique course records')
    names=profile_names()
    chosen_sample=st.selectbox('Synthetic example', ['Custom']+names, index=1 if names else 0)
    example=load_example(chosen_sample) if chosen_sample!='Custom' else {}
    default_program=example.get('program_id') if example.get('program_id') in cat.programs else programs[0]
    program=st.selectbox('Degree program',programs,index=programs.index(default_program),format_func=lambda x:labels[x],key=f'program_{chosen_sample}')
    st.markdown('**Data references**')
    st.link_button('Official program requirements',cat.programs[program]['source_url'])
    st.caption('Program definitions live in catalog/programs/*.json; restart the app after adding files.')

prog=cat.programs[program]
base=example if example.get('program_id')==program else {}
base_done={x['course_id']:x for x in base.get('completed_courses',[])}
real_done=[x for x in base_done if x in cat.courses and course_credits(cat.courses[x]) is not None]
slot_done=[x[:-5] for x in base_done if x.endswith('_SLOT')]
slot_done.extend(base.get('completed_slots',[]))
all_slots=cat.templates[prog['gened_template']]['slots']
other_slots=prog.get('other_slots',[])
all_courses=sorted(c for c,info in cat.courses.items() if course_credits(info) is not None)
flags_config=json.loads((Path(__file__).parent/'catalog'/'profile_flags.json').read_text(encoding='utf-8'))

profile_key=chosen_sample+'_'+program
with st.form('academic_profile_'+profile_key):
    st.subheader('1 · Student academic record')
    st.caption('Only synthetic/sample data. A real transcript or DARS export is not connected.')
    a,b=st.columns(2)
    with a:campus=st.selectbox('Campus preference', ['Tokyo','Kyoto','Either'],key=f'campus_{profile_key}',index=['Tokyo','Kyoto','Either'].index(base.get('campus_preference','Tokyo')))
    with b:target=st.slider('Target credits per relative term',9,21,int(base.get('preferences',{}).get('target_credits_per_term',15)))
    completed=st.multiselect('Completed course IDs',all_courses,default=real_done,key=f'completed_{profile_key}',
        format_func=lambda c:f"{c} · {cat.courses[c]['title']} ({course_credits(cat.courses[c]):g} cr.)")
    grades={}
    with st.expander('Recorded grades / transfer designation',expanded=False):
        external=[]
        for cid in completed:
            lc,rc=st.columns([3,1]); row=base_done.get(cid,{})
            with lc:grades[cid]=st.selectbox(f'{cid} grade',['A','A-','B+','B','B-','C+','C','C-','D','F'],
                                               index=['A','A-','B+','B','B-','C+','C','C-','D','F'].index(row.get('grade','B') if row.get('grade','B') in ['A','A-','B+','B','B-','C+','C','C-','D','F'] else 'B'),key=f'grade_{profile_key}_{cid}')
            with rc:
                if st.checkbox('Transfer',value=not row.get('at_temple',True),key=f'transfer_{chosen_sample}_{program}_{cid}'):
                    external.append(cid)
    col1,col2=st.columns(2)
    with col1:
        gened=st.multiselect('Completed GenEd areas (provisional)',[s['id'] for s in all_slots],
             default=[x for x in slot_done if x in {s['id'] for s in all_slots}],key=f'gened_{profile_key}',
             format_func=lambda x:next(s['label']+f' ({x})' for s in all_slots if s['id']==x))
    with col2:
        others=st.multiselect('Completed/waived other academic slots',[s['id'] for s in other_slots],
          default=[x for x in slot_done if x in {s['id'] for s in other_slots}],key=f'other_slots_{profile_key}',
          format_func=lambda x:next(s['label'] for s in other_slots if s['id']==x))
    other_credits=st.number_input('Other completed credits (unmapped; requires review)',0,120,int(base.get('other_completed_credits',0)),key=f'other_credits_{profile_key}')
    with st.expander('Documented eligibility flags — synthetic demonstration',expanded=False):
        flag_values={}
        default_flags=base.get('prototype_flags',{})
        cols=st.columns(2)
        for i,(flag,label) in enumerate(flags_config.items()):
            with cols[i%2]:flag_values[flag]=st.checkbox(label,value=bool(default_flags.get(flag,False)),key=f'flag_{chosen_sample}_{program}_{flag}')
    st.subheader('2 · Student interests and career direction')
    st.caption('Weights represent the student’s own ratings, **not** psychological scores. 0 = no preference, 5 = high preference.')
    # Only show interests which appear in the selected program's listed course options.
    ids={cid for group in prog['groups'] for b in group['choices'] for cid in b}
    relevant=sorted({tag for cid in ids for tag in cat.courses[cid].get('tags',{})})
    default_interest=base.get('preferences',{}).get('interest_weights',{})
    ratings={}
    with st.expander('Rate subject interests',expanded=True):
        columns=st.columns(3)
        for i,tag in enumerate(relevant):
            with columns[i%3]:
                ratings[tag]=st.slider(cat.interest_labels[tag],0,5,int(default_interest.get(tag,0)),key=f'weight_{chosen_sample}_{program}_{tag}')
    careers=st.multiselect('Career interest tags',relevant,
             default=[x for x in base.get('preferences',{}).get('career_tags',[]) if x in relevant],
             format_func=lambda x:cat.interest_labels[x],key=f'careers_{profile_key}')
    submitted=st.form_submit_button('Generate academic pathways',type='primary',use_container_width=True)

if submitted:
    try:
        student=build_student(cat,program_id=program,course_ids=completed,grades=grades,gened_ids=gened,
             other_slots=others,interests=ratings,careers=careers,flags=flag_values,target=target,
             campus=campus,other_credits=int(other_credits),temple_ids=[c for c in completed if c not in external])
        with st.spinner('Calculating rule-based pathways…'):
            report=assess(cat,student)
        st.session_state['owlpath_report']=report
        st.session_state['owlpath_display_key']=chosen_sample+'|'+program
    except (ValueError,KeyError) as exc:
        st.error(str(exc));st.stop()
report=st.session_state.get('owlpath_report')
if report is None:
    st.info('Select a synthetic profile or enter a custom profile, then generate plans. The engine automatically discovers supported majors from the catalog.')
    st.stop()

st.divider();st.subheader('3 · Compare proposed pathways')
if report['program_id']!=program or st.session_state.get('owlpath_display_key') != chosen_sample+'|'+program:
    st.info('Generate pathways for the newly selected student or program to replace the previous report.')
    st.stop()

names={'fastest':'Prerequisite-first','balanced':'Balanced workload','interest':'Interest aligned'}
cols=st.columns(3)
for col,strategy in zip(cols,names):
    with col:
        info=report['plans'][strategy]
        st.markdown('**'+names[strategy]+'**')
        if info['ok']:
            plan=info['plan'];st.metric('Relative terms',len(plan['terms']))
            st.caption(f"Projected credits {plan['projected_total_credits']:g} · {plan['verification']['provisional_slots']} provisional slots")
        else:
            st.error('BLOCKED')
            st.caption(info['error'])
options=list(names)
chosen=st.radio('Inspect a proposal',options,index=2,format_func=lambda x:names[x],horizontal=True)
info=report['plans'][chosen]
if not info['ok']:
    st.error('No modeled-valid plan generated: '+str(info['error']))
else:
    plan=info['plan'];v=plan['verification']
    st.success(v['status'])
    st.markdown(explain_locally(report,chosen,cat))
    left,right=st.columns([1.5,1])
    with left:
        st.markdown('#### Semester-by-semester proposal')
        for sem in plan['terms']:
            with st.expander(f"Relative term {sem['term']} · {sem['credits']:g} credits",expanded=sem['term']<3):
                table=[{'Course or slot':x['id'],'Description':x['title'],
                        'Credits':x['credits'],'Type':x['kind'].replace('_',' ')} for x in sem['items']]
                st.dataframe(table,hide_index=True,use_container_width=True)
    with right:
        st.markdown('#### Requirement selection')
        for group in cat.programs[report['program_id']]['groups']:
            selected=plan['group_choices'].get(group['id'],[])
            with st.expander(group['label'],expanded=False):
                st.write('; '.join(' + '.join(s) for s in selected) or 'No selection')
        st.markdown('#### Validation & required human review')
        st.caption('Requirement groups are checked; final academic eligibility is **not** certified.')
        st.metric('Modeled rule groups',f"{sum(g['passed'] for g in v['group_results'])}/{len(v['group_results'])}")
        st.warning('TUJ offerings are not verified. General education, language and free credits can be placeholders.')
        for check in v['checks']:
            st.caption(f"{check['id']} · {check['status']} · {check['result']}")

    st.markdown('#### Optional AI explanation and questions')
    st.caption('Only the selected plan, interests, career tags, modeled warnings and your question are sent to the external API; no name or grades.')
    if not os.getenv('OPENAI_API_KEY'):
        st.info('Set OPENAI_API_KEY to enable AI Q&A. The local pathway explanation works without any API key.')
    question=st.text_input('Question about the selected pathway',value='Why are these electives suitable for my interests?',key='question_'+chosen)
    answer_key='ai_answer_'+fingerprint(report,chosen)
    if st.button('Explain with AI',disabled=not bool(os.getenv('OPENAI_API_KEY')),key='explain_'+chosen):
        try:
            with st.spinner('Generating a grounded explanation…'):
                st.session_state[answer_key]=explain_with_openai(report,chosen,question)
        except (RuntimeError,ValueError) as exc:st.error(str(exc))
    if answer_key in st.session_state:st.info(st.session_state[answer_key])

st.divider();st.subheader('4 · Advisor review (provisional)')
st.caption('A simulated advisor can comment; this does not record official Temple approval.')
reviews=st.session_state.setdefault('owlpath_reviews',{})
key=fingerprint(report,chosen)
previous=reviews.get(key,{})
with st.form('advisor_'+key):
    opts=['Not reviewed','Discussed — preliminary','Revision requested']
    status=st.selectbox('Review status',opts,index=opts.index(previous.get('status','Not reviewed')))
    comment=st.text_area('Advisor comments',value=previous.get('comment',''),height=95,max_chars=2000)
    saved=st.form_submit_button('Save provisional review')
if saved:
    reviews[key]={'status':status,'comment':comment}
    st.success('Provisional review saved in this browser session only.')
review=reviews.get(key,{})
st.markdown('#### Export')
st.download_button('Download complete model report (JSON)',json.dumps(report,indent=2,ensure_ascii=False),file_name='owlpath_report.json',mime='application/json')
st.download_button('Download advising brief (Markdown)',advisor_markdown(cat,report,chosen,review),file_name='owlpath_advising_brief.md',mime='text/markdown')
st.caption('To add a major: add its data file under catalog/programs and any new course/prerequisite records in catalog. No Python conditional for a major is required.')
